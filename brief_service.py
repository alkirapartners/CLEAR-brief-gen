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
from briefparse import clean_brief, extract_company_header, extract_score
from errors import (
    BriefNotFound, DailyLimitReached, GenerationInFlight, NotConfigured, SaveFailed,
)
from settings import Settings
from streaming import PhaseCallback, Work

logger = logging.getLogger(__name__)

SAVE_ATTEMPTS = 2

IN_FLIGHT_MESSAGE = (
    "A brief is already being written for you. It will appear in your briefs when it finishes."
)
NOT_CONFIGURED_MESSAGE = "Brief generation is not available right now. Please try again later."
SAVE_FAILED_MESSAGE = "The brief was written but could not be saved. Please try again."
NOT_FOUND_MESSAGE = "Brief not found"


class InFlightGuard:
    """At most one generation per user in this process."""

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
    def __init__(self, repo: Any, generator: Callable[..., str], settings: Settings) -> None:
        self._repo = repo
        self._generator = generator
        self._settings = settings
        self._guard = InFlightGuard()

    # ── Public ───────────────────────────────────────────────────

    def start_generate(self, email: str, company: str, language: str) -> Work:
        self._acquire(email)
        try:
            cached = self._reusable(company, language)
            if cached is None:
                self._require_capacity(email)
        except Exception:
            self._guard.release(email)
            raise

        def work(on_phase: PhaseCallback) -> dict:
            try:
                if cached is not None:
                    research_date = cached.get("created_at") or None
                    return self._save(
                        email, company, cached["brief_md"],
                        created_at=research_date, reused_from=research_date,
                    )
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
            self._require_capacity(email)
        except Exception:
            self._guard.release(email)
            raise

        company = old.get("company") or ""
        target_language = (
            i18n.normalize(language) if language
            else i18n.detect_language(old.get("brief_md") or "")
        )

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

    def _require_capacity(self, email: str) -> None:
        if not self._settings.anthropic_key or not self._settings.tavily_key:
            raise NotConfigured(NOT_CONFIGURED_MESSAGE)
        limit = self._settings.daily_limit
        start_of_day = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        if self._repo.count_user_briefs_since(email, start_of_day.isoformat()) >= limit:
            raise DailyLimitReached(
                f"You've reached today's limit of {limit} briefs. It resets at midnight UTC."
            )

    def _run_generator(self, company: str, language: str, on_phase: PhaseCallback) -> str:
        return self._generator(
            self._settings.anthropic_key, self._settings.tavily_key,
            company, on_phase, language=language,
        )

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
            logger.error("Brief for %s / %s could not be saved", email, typed_company)
            raise SaveFailed(SAVE_FAILED_MESSAGE)
        return {"type": "done", "briefId": saved["id"], "reusedFrom": reused_from}
