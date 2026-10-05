"""The rules for producing a brief: reuse, generate, save, refresh.

Lifted from the Streamlit page's main(). Each start_* method does every
check that can fail fast (in flight, not found, daily cap, configuration)
and returns the blocking job to run; the job saves the brief itself.
"""

import logging
import threading
from datetime import datetime, timezone
from typing import Any, Callable

import i18n
from briefparse import (
    MAX_COMPANY_PREFILL_CHARS, clean_brief, extract_company_header, extract_score,
)
from errors import (
    BriefNotFound, DailyLimitReached, GenerationInFlight, NotConfigured, SaveFailed,
    UserFacingError,
)
from settings import Settings
from streaming import PhaseCallback, Work
from usage_ledger import LedgerError, UsageLedger

logger = logging.getLogger(__name__)

SAVE_ATTEMPTS = 2

IN_FLIGHT_MESSAGE = (
    "A brief is already being written for you. It will appear in your briefs when it finishes."
)
NOT_CONFIGURED_MESSAGE = "Brief generation is not available right now. Please try again later."
SAVE_FAILED_MESSAGE = "The brief was written but could not be saved. Please try again."
NOT_FOUND_MESSAGE = "Brief not found"
NO_COMPANY_MESSAGE = "This brief has no company name to research. Generate a new brief instead."

Clock = Callable[[], datetime]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _clean_stored_company(raw: str | None) -> str:
    """A stored company name, made safe to search and prompt with.

    The stored name is the heading the model wrote, not what a partner typed,
    so it gets the same flattening as typed input and is cut to the same limit.
    """
    printable = "".join(ch if ch.isprintable() else " " for ch in (raw or ""))
    return " ".join(printable.split())[:MAX_COMPANY_PREFILL_CHARS].strip()


class InFlightGuard:
    """At most one generation per user in this process.

    Production runs two instances, so a user who reaches both can run two at
    once. The daily cap is shared between instances; this guard is not.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._emails: set[str] = set()

    def acquire(self, email: str) -> bool:
        with self._lock:
            if email in self._emails:
                return False
            self._emails.add(email)
            return True

    def release(self, email: str) -> None:
        with self._lock:
            self._emails.discard(email)


class BriefService:
    def __init__(
        self,
        repo: Any,
        generator: Callable[..., str],
        settings: Settings,
        ledger: UsageLedger,
        clock: Clock = _utc_now,
    ) -> None:
        self._repo = repo
        self._generator = generator
        self._settings = settings
        self._ledger = ledger
        self._clock = clock
        self._guard = InFlightGuard()

    # ── Public ───────────────────────────────────────────────────

    def start_generate(self, email: str, company: str, language: str) -> Work:
        self._acquire(email)
        try:
            cached = self._reusable(company, language)
            if cached is None:
                self._reserve_generation(email)
        except BaseException:
            self._guard.release(email)
            raise

        def work(on_phase: PhaseCallback) -> dict:
            try:
                if cached is not None:
                    return self._reuse(email, company, cached)
                raw = self._run_generator(company, language, on_phase)
                return self._save(email, company, raw, created_at=None, reused_from=None)
            finally:
                self._guard.release(email)

        return work

    def start_refresh(self, email: str, brief_id: str, language: str | None) -> Work:
        self._acquire(email)
        try:
            old = self._repo.get_brief(brief_id, email)
            if old is None:
                raise BriefNotFound(NOT_FOUND_MESSAGE)
            company = _clean_stored_company(old.get("company"))
            if not company:
                raise UserFacingError(NO_COMPANY_MESSAGE)
            target_language = (
                i18n.normalize(language) if language
                else i18n.detect_language(old.get("brief_md") or "")
            )
            self._reserve_generation(email)
        except BaseException:
            self._guard.release(email)
            raise

        def work(on_phase: PhaseCallback) -> dict:
            try:
                raw = self._run_generator(company, target_language, on_phase)
                done = self._save(email, company, raw, created_at=None, reused_from=None)
                # Save first, remove second: a failed refresh never costs the old brief.
                if not self._repo.delete_brief(old["id"], email):
                    logger.warning("Refreshed brief %s but could not remove the old copy", old["id"])
                return done
            finally:
                self._guard.release(email)

        return work

    def abandon(self, email: str) -> None:
        """Release the guard for a job that was prepared but could not be started."""
        self._guard.release(email)

    # ── Internals ────────────────────────────────────────────────

    def _acquire(self, email: str) -> None:
        if not self._guard.acquire(email):
            raise GenerationInFlight(IN_FLIGHT_MESSAGE)

    def _reusable(self, company: str, language: str) -> dict | None:
        cached = self._repo.find_recent_brief_by_company(company)
        # Stored briefs carry no language column, so read the brief itself.
        # A mismatch only costs one regeneration.
        if cached and i18n.detect_language(cached.get("brief_md") or "") != language:
            return None
        return cached

    def _reserve_generation(self, email: str) -> None:
        """Check the daily cap and count this generation against it.

        Counted when the job is accepted, not when a brief is saved, so a
        generation that fails after spending money still counts, and deleting
        or updating a brief never gives one back. If usage cannot be read or
        written the generation is refused rather than let through uncounted.
        """
        if not self._settings.anthropic_key or not self._settings.tavily_key:
            raise NotConfigured(NOT_CONFIGURED_MESSAGE)
        limit = self._settings.daily_limit
        now = self._clock()
        try:
            used = self._ledger.count_on_day(email, now.date())
            if used < limit:
                self._ledger.record(email, now)
        except LedgerError as exc:
            logger.error("Usage ledger unavailable, refusing generation for %s: %s", email, exc)
            raise NotConfigured(NOT_CONFIGURED_MESSAGE) from exc
        if used >= limit:
            raise DailyLimitReached(
                f"You've reached today's limit of {limit} briefs. It resets at midnight UTC."
            )

    def _run_generator(self, company: str, language: str, on_phase: PhaseCallback) -> str:
        return self._generator(
            self._settings.anthropic_key, self._settings.tavily_key,
            company, on_phase, language=language,
        )

    def _reuse(self, email: str, typed_company: str, cached: dict) -> dict:
        """Give the caller this research, without copying what they already hold."""
        research_date = cached.get("created_at") or None
        existing = self._existing_copy(email, cached)
        if existing is not None:
            return {"type": "done", "briefId": existing["id"], "reusedFrom": research_date}
        return self._save(
            email, typed_company, cached["brief_md"],
            created_at=research_date, reused_from=research_date,
        )

    def _existing_copy(self, email: str, cached: dict) -> dict | None:
        """The caller's own row for this research: the original, or an earlier copy of it."""
        if (cached.get("email") or "").strip().lower() == email.strip().lower():
            return cached
        company = (cached.get("company") or "").strip().casefold()
        for row in self._repo.get_user_briefs(email):
            same_research = row.get("created_at") == cached.get("created_at")
            if same_research and (row.get("company") or "").strip().casefold() == company:
                return row
        return None

    def _save(
        self, email: str, typed_company: str, raw: str,
        created_at: str | None, reused_from: str | None,
    ) -> dict:
        brief_md = clean_brief(raw)
        score, _ = extract_score(brief_md)
        company, _ = extract_company_header(brief_md)
        saved = None
        for _attempt in range(SAVE_ATTEMPTS):
            saved = self._repo.save_brief(
                email, company or typed_company, score, brief_md, created_at=created_at
            )
            if saved:
                break
        if not saved:
            # The text is logged so a brief that was paid for can be recovered by hand.
            logger.error(
                "Brief for %s / %s could not be saved. Its text follows.\n%s",
                email, typed_company, brief_md,
            )
            raise SaveFailed(SAVE_FAILED_MESSAGE)
        return {"type": "done", "briefId": saved["id"], "reusedFrom": reused_from}
