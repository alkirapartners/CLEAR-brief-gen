"""The command-line tool and the readable text it prints. No live API calls."""

import json

import pytest

import brief_text
import generate
import generate_brief
import llm
from research_loop import ResearchResult
from tests.brief_fixtures import SAMPLE_JSON_BRIEF, make_doc


def _generation(doc=None):
    doc = doc or make_doc()
    found = ResearchResult(
        sources=(), searches=21, page_reads=18, pages_opened=17, seconds=203.4,
        stopped_by="finished", usage=llm.Usage(),
    )
    usage = llm.Usage(requests=14, input_tokens=9000, output_tokens=7000, cache_read_tokens=400000)
    return generate.Generation(json.dumps(doc, ensure_ascii=False), doc, found, usage, 231.6, 0.874)


@pytest.fixture
def cli(monkeypatch):
    """Run the tool with keys set and generation replaced by a canned brief."""
    calls = []

    def fake(api_key, tavily_key, company, status, language="en"):
        calls.append((api_key, tavily_key, company, language))
        for phase in ("init", "research", "analyze", "compose", "done"):
            status(phase)
        return _generation()

    monkeypatch.setattr(generate_brief, "load_dotenv", lambda *args, **kwargs: False)
    monkeypatch.setattr(generate_brief.generate, "generate_detailed", fake)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a-key")
    monkeypatch.setenv("TAVILY_API_KEY", "t-key")
    return calls


# ── Readable text ────────────────────────────────────────────────

def test_the_text_shows_every_part_of_the_brief():
    text = brief_text.render(make_doc())
    for expected in (
        "# Northwind Energy",
        "Entity: Northwind Energy Corporation (NYSE: NWE) | HQ: Dallas, TX",
        "Which company: Researched Northwind Energy Corporation",
        "## Alkira Fit: 5 / 5",
        "Lead with: Open with the Azure hub build",
        "## Why this account, why now",
        "### 1. Hand-built Azure network (multi_cloud)",
        "- A network engineer posting lists ExpressRoute and a Virtual WAN hub-and-spoke. (source dated 23 Sep 2026) [1]",
        "Customer story: Koch Industries: Significant reduction",
        "## Technical snapshot",
        "- Data centers: Not found",
        "- Chief Information Officer (Dana Ruiz): Named in the annual report. [2]",
        "1. Who builds a new Virtual WAN hub today, and how long does one take?",
        "   Listen for: hand-built hubs, weeks of lead time",
        "## What we couldn't confirm",
        "## What would raise the score",
        "[2] Annual report — https://www.northwind.example/annual-report.pdf",
        "Research: 21 searches, 17 pages opened, 203 s, stopped by finished. Generated 2026-10-05.",
    ):
        assert expected in text, f"missing from the text: {expected!r}"


def test_a_brief_with_no_angles_prints_no_empty_sections():
    fit = {"score": 1, "verdict": "No use case found.", "lead": ""}
    text = brief_text.render(make_doc(angles=[], fit=fit, people=[], questions=[], unconfirmed=[], raise_score=[]))
    assert "## Alkira Fit: 1 / 5" in text and "## Technical snapshot" in text
    for absent in ("Why this account", "Who to talk to", "Questions to ask", "Lead with"):
        assert absent not in text


def test_a_spanish_brief_prints_spanish_headings():
    text = brief_text.render(make_doc(language="es"))
    assert "## Panorama técnico" in text and "- Centros de datos: No encontrado" in text


# ── The tool ─────────────────────────────────────────────────────

def test_it_prints_the_brief_and_one_line_of_metrics(cli, capsys):
    generate_brief.main(["HF Sinclair", "--language", "es"])
    out = capsys.readouterr().out
    assert cli == [("a-key", "t-key", "HF Sinclair", "es")]
    assert "# Northwind Energy" in out and "[research]" not in out
    record = json.loads(out.strip().splitlines()[-1])
    assert record["company"] == "HF Sinclair" and record["resolved"] == "Northwind Energy"
    assert (record["score"], record["angles"], record["seconds"]) == (5, 2, 232)
    assert (record["searches"], record["pages_opened"], record["stopped_by"]) == (21, 17, "finished")
    assert record["requests"] == 14 and record["cache_read_tokens"] == 400000
    assert record["cost_usd"] == 0.874
    assert record["tavily_credits"] == pytest.approx(21 * 2 + 17 * 0.4)
    assert record["not_covered"] == []


def test_verbose_shows_the_phases(cli, capsys):
    generate_brief.main(["Acme", "--verbose"])
    out = capsys.readouterr().out
    assert out.index("[init]") < out.index("[research]") < out.index("[compose]") < out.index("[done]")


def test_output_saves_the_readable_text(cli, tmp_path, capsys):
    target = tmp_path / "brief.md"
    generate_brief.main(["Acme", "--output", str(target)])
    assert target.read_text(encoding="utf-8") == brief_text.render(make_doc())


def test_save_dir_writes_json_text_pdf_and_appends_metrics(cli, tmp_path, capsys):
    out_dir = tmp_path / "eval"
    generate_brief.main(["HF Sinclair", "--save-dir", str(out_dir)])
    generate_brief.main(["Southern Glazer's", "--save-dir", str(out_dir)])
    assert (out_dir / "hf-sinclair.json").read_text(encoding="utf-8") == SAMPLE_JSON_BRIEF
    assert (out_dir / "hf-sinclair.md").read_text(encoding="utf-8").startswith("# Northwind Energy")
    assert (out_dir / "hf-sinclair.pdf").read_bytes().startswith(b"%PDF-")
    assert (out_dir / "southern-glazer-s.json").exists()
    lines = (out_dir / "metrics.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["company"] for line in lines] == ["HF Sinclair", "Southern Glazer's"]


def test_without_keys_it_stops_before_generating(cli, monkeypatch, capsys):
    monkeypatch.delenv("TAVILY_API_KEY")
    with pytest.raises(SystemExit) as stop:
        generate_brief.main(["Acme"])
    assert stop.value.code == 1 and cli == []
    assert "must be set" in capsys.readouterr().out
