"""The probe's verdict. The probe itself runs on a server; nothing here calls out."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "probe_research_tools.py"
_spec = importlib.util.spec_from_file_location("probe_research_tools", SCRIPT)
probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(probe)

LONG = 20_000
URLS = [url for url, _marker in probe.CAREERS_PAGES]
WORKDAY = "https://oxy.wd5.myworkdayjobs.com/en-US/Corporate"
JOB_LIST = "[Network Engineer](https://oxy.wd5.myworkdayjobs.com/en-US/Corporate/job/Houston/Network-Engineer_JR1) Posted Today. " * 40
# What a fetch without JavaScript gets from a Workday job list: the page's description, no jobs.
METADATA_ONLY = "meta-description: Oxy has bold ambitions to achieve net zero. Introduce yourself to our recruiters. " * 30


def _report(anthropic_reads=(LONG, 0, 0, LONG, LONG), tavily_reads=(LONG,) * 5, **changes):
    report = {
        "model": "ok", "refusal_fallback": "ok", "strict_tool": "ok", "structured_output": "ok",
        "tavily_search": 3, "tavily_pdf": 850_000,
        "careers": {
            url: {"tavily": tavily, "anthropic": anthropic}
            for url, tavily, anthropic in zip(URLS, tavily_reads, anthropic_reads)
        },
    }
    report.update(changes)
    return report


def test_tavily_is_chosen_when_it_reads_careers_sites_anthropic_cannot():
    verdict, reason = probe.decide(_report())
    assert verdict == "tavily"
    assert "Tavily read 5 of 5" in reason and "web fetch read 3" in reason


def test_an_error_a_near_empty_page_or_a_page_without_its_job_list_does_not_count_as_read():
    """Length is not enough: a Workday page fetched without JavaScript is long and lists no jobs."""
    marker = dict(probe.CAREERS_PAGES)[WORKDAY]
    assert probe.page_result(JOB_LIST, "", marker) == len(JOB_LIST)
    unread = probe.page_result(METADATA_ONLY, "", marker)
    assert unread == f"{len(METADATA_ONLY)} characters, none of them a job listing"
    assert probe.page_result("", "url_not_accessible", marker) == "url_not_accessible"
    reads = ("url_not_accessible", 40, unread, LONG, LONG)
    assert probe.decide(_report(anthropic_reads=reads))[0] == "tavily"


def test_anthropic_reading_everything_stops_the_plan_for_revision():
    verdict, reason = probe.decide(_report(anthropic_reads=(LONG,) * 5))
    assert verdict == "anthropic" and "revised" in reason


def test_a_failed_claude_check_blocks():
    assert probe.decide(_report(strict_tool="no tool call (end_turn)"))[0] == "blocked"
    assert probe.decide(_report(model="NotFoundError: model"))[0] == "blocked"
    assert probe.decide(_report(structured_output="BadRequestError: x"))[0] == "blocked"


def test_a_missing_refusal_fallback_does_not_block():
    """It is optional: llm.USE_REFUSAL_FALLBACK is set from this line of the report."""
    assert probe.decide(_report(refusal_fallback="BadRequestError: unknown beta"))[0] == "tavily"


def test_tavily_not_working_blocks():
    assert probe.decide(_report(tavily_search="InvalidAPIKeyError: x"))[0] == "blocked"
    assert probe.decide(_report(tavily_pdf="not extracted"))[0] == "blocked"
    assert probe.decide(_report(tavily_reads=(LONG, 0, 0, LONG, LONG)))[0] == "blocked"


def test_run_builds_a_full_report_from_the_two_clients():
    class Web:
        def search(self, query, **kwargs):
            return {"results": [{"url": "https://example.com"}]}

        def extract(self, urls, **kwargs):
            return {"results": [{"url": urls[0], "raw_content": JOB_LIST}]}

    def create(**kwargs):
        if "output_config" in kwargs:
            return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text='{"score": 3}')])
        tools = kwargs.get("tools") or []
        if tools and tools[0].get("type") == "web_fetch_20260209":
            page = SimpleNamespace(content=SimpleNamespace(source=SimpleNamespace(data=METADATA_ONLY)))
            page.type = "web_fetch_result"
            return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="web_fetch_tool_result", content=page)])
        if tools:
            call = SimpleNamespace(type="tool_use", input={"word": "probe"})
            return SimpleNamespace(stop_reason="tool_use", content=[call])
        return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text="OK")])

    client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=create)))
    report = probe.run(client, Web())
    assert report["model"] == report["refusal_fallback"] == report["strict_tool"] == report["structured_output"] == "ok"
    assert report["tavily_pdf"] == len(JOB_LIST) and report["tavily_search"] == 1
    assert set(report["careers"]) == set(URLS)
    assert report["careers"][WORKDAY] == {
        "tavily": len(JOB_LIST),
        "anthropic": f"{len(METADATA_ONLY)} characters, none of them a job listing",
    }
    assert report["verdict"] == "tavily"
