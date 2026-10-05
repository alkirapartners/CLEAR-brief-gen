"""Append-only record of paid brief generations, for the daily cap.

One small file per UTC day in the shared data directory (EFS in production),
so both instances see the same count and it survives restarts.

The cap cannot be read from the briefs table: deleting a brief, or updating
one (which swaps the old row for a new one), removes the row that was counted
and would hand the generation back.
"""

import json
import logging
import os
from datetime import date, datetime, timedelta

logger = logging.getLogger(__name__)

FILE_PREFIX = "brief-usage-"
FILE_SUFFIX = ".jsonl"
# Only today's file is ever read; a week is kept for looking into a complaint.
KEEP_DAYS = 7


class LedgerError(Exception):
    """The ledger could not be read or written."""


def _normalize(email: str) -> str:
    return email.strip().lower()


class UsageLedger:
    def __init__(self, directory: str) -> None:
        self._directory = directory

    def record(self, email: str, when: datetime) -> None:
        """Note one generation. Raises LedgerError if it could not be written."""
        line = json.dumps({"email": _normalize(email), "at": when.isoformat()})
        try:
            os.makedirs(self._directory, exist_ok=True)
            with open(self._path(when.date()), "a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        except OSError as exc:
            raise LedgerError(f"could not record usage: {exc}") from exc
        self._prune(when.date())

    def count_on_day(self, email: str, day: date) -> int:
        """Generations recorded for this person on this UTC day.

        Raises LedgerError rather than returning zero when the file cannot be
        read, so unhealthy storage never silently lifts the cap.
        """
        wanted = _normalize(email)
        try:
            with open(self._path(day), encoding="utf-8") as handle:
                lines = handle.readlines()
        except FileNotFoundError:
            return 0
        except OSError as exc:
            raise LedgerError(f"could not read usage: {exc}") from exc

        count = 0
        for line in lines:
            try:
                entry = json.loads(line)
            except ValueError:
                continue  # a torn write from a crash; one lost count is harmless
            if isinstance(entry, dict) and entry.get("email") == wanted:
                count += 1
        return count

    def _path(self, day: date) -> str:
        return os.path.join(self._directory, f"{FILE_PREFIX}{day.isoformat()}{FILE_SUFFIX}")

    def _prune(self, today: date) -> None:
        """Remove this ledger's own files once they are older than KEEP_DAYS. Best effort."""
        cutoff = today - timedelta(days=KEEP_DAYS)
        try:
            names = os.listdir(self._directory)
        except OSError:
            return
        for name in names:
            if not (name.startswith(FILE_PREFIX) and name.endswith(FILE_SUFFIX)):
                continue
            stamp = name[len(FILE_PREFIX):-len(FILE_SUFFIX)]
            try:
                is_old = date.fromisoformat(stamp) < cutoff
            except ValueError:
                continue
            if is_old:
                try:
                    os.remove(os.path.join(self._directory, name))
                except OSError as exc:
                    logger.warning("Could not remove old usage file %s: %s", name, exc)
