"""In-memory stand-ins for the database and the brief generator."""

import json
from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from settings import Settings
from tests.test_pdf import SAMPLE_FULL_BRIEF

SAMPLE_BRIEF = SAMPLE_FULL_BRIEF
AUTH = {"X-Auth-Email": "Partner@Example.com"}
OTHER = {"X-Auth-Email": "someone@else.com"}
TEST_SETTINGS = Settings(
    anthropic_key="test-anthropic", tavily_key="test-tavily",
    daily_limit=50, admins_file="/nonexistent/admins.json",
)


class FakeRepo:
    """Same function names as db.py, backed by a list."""

    def __init__(self, rows=None):
        self.rows = list(rows or [])
        self.save_failures = 0

    def seed(self, email, company="TestCo Holdings", brief_md=SAMPLE_BRIEF,
             created_at=None, score=4):
        row = {
            "id": str(uuid4()), "email": email.lower(), "company": company,
            "score": score, "brief_md": brief_md,
            "created_at": created_at or datetime.now(timezone.utc).isoformat(),
        }
        self.rows.append(row)
        return row

    def get_user_briefs(self, email):
        mine = [r for r in self.rows if r["email"] == email.lower()]
        return sorted(mine, key=lambda r: r["created_at"], reverse=True)

    def get_brief(self, brief_id, email):
        for row in self.rows:
            if row["id"] == brief_id and row["email"] == email.lower():
                return row
        return None

    def save_brief(self, email, company, score, brief_md, created_at=None):
        if self.save_failures > 0:
            self.save_failures -= 1
            return None
        return self.seed(email, company, brief_md, created_at, score)

    def delete_brief(self, brief_id, email):
        before = len(self.rows)
        self.rows = [
            r for r in self.rows
            if not (r["id"] == brief_id and r["email"] == email.lower())
        ]
        return len(self.rows) < before

    def find_recent_brief_by_company(self, company, max_age_days=7):
        wanted = company.strip().lower()
        matches = [r for r in self.rows if r["company"].lower() == wanted]
        return max(matches, key=lambda r: r["created_at"]) if matches else None

    def count_user_briefs_since(self, email, since_iso):
        return len([
            r for r in self.rows
            if r["email"] == email.lower() and r["created_at"] >= since_iso
        ])


def fake_generator(api_key, tavily_key, company, status_callback,
                   timeout_seconds=180, language="en"):
    for phase in ("init", "research", "analyze", "compose", "done"):
        status_callback(phase)
    return SAMPLE_BRIEF


def make_client(repo=None, generator=fake_generator, settings=TEST_SETTINGS,
                heartbeat_seconds=15.0):
    from server import create_app
    app = create_app(
        repo=repo if repo is not None else FakeRepo(),
        generator=generator, settings=settings,
        heartbeat_seconds=heartbeat_seconds,
    )
    return TestClient(app)


def events(response):
    return [
        json.loads(line[len("data: "):])
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
