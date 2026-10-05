"""The parsers and the PDF renderer must work without Streamlit installed."""

import subprocess
import sys


def test_briefparse_and_pdf_do_not_import_streamlit():
    code = (
        "import sys, briefparse, pdf\n"
        "from tests.test_pdf import SAMPLE_FULL_BRIEF\n"
        "pdf.generate_brief_pdf(SAMPLE_FULL_BRIEF, 'TestCo Holdings', 4)\n"
        "assert 'streamlit' not in sys.modules, 'streamlit was imported'\n"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
