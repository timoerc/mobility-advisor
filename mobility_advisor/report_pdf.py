"""Convert the annual report's Markdown text into a branded, print-ready PDF.

Mirrors the fixed Markdown structure produced by annual_communicator_agent (see
sub_agents.py) into an HTML document styled by mobility_advisor/templates/
annual_report.css, then rasterizes it to PDF bytes via WeasyPrint.
"""
from pathlib import Path

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_HTML_TEMPLATE_PATH = _TEMPLATES_DIR / "annual_report.html"
_CSS_PATH = _TEMPLATES_DIR / "annual_report.css"


def render_annual_report_pdf(report_markdown: str) -> bytes:
    """Render the annual_communicator's Markdown report as a styled PDF.

    markdown and weasyprint are imported here, not at module level: weasyprint
    pulls in native Pango/Cairo bindings, and a missing/broken system install
    should only ever break this one call, not main.py's startup or any other
    endpoint.
    """
    import markdown
    from weasyprint import HTML

    body_html = markdown.markdown(report_markdown, extensions=["tables", "sane_lists"])
    page_html = _HTML_TEMPLATE_PATH.read_text().replace("{{body}}", body_html)
    return HTML(string=page_html, base_url=str(_TEMPLATES_DIR)).write_pdf(
        stylesheets=[str(_CSS_PATH)]
    )
