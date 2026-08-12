"""Convert the annual report's Markdown text into a branded, print-ready PDF.

Mirrors the fixed Markdown structure produced by annual_communicator_agent (see
agents/annual.py) into an HTML document styled by reporting/templates/annual_report.css,
then rasterizes it to PDF bytes via WeasyPrint.
"""
from .. import paths


def render_annual_report_pdf(report_markdown: str) -> bytes:
    """Render the annual_communicator's Markdown report as a styled PDF.

    markdown and weasyprint are imported here, not at module level: weasyprint
    pulls in native Pango/Cairo bindings, and a missing/broken system install
    should only ever break this one call, not app startup or any other endpoint.
    """
    import markdown
    from weasyprint import HTML

    html_path = paths.TEMPLATES_DIR / "annual_report.html"
    css_path = paths.TEMPLATES_DIR / "annual_report.css"

    body_html = markdown.markdown(report_markdown, extensions=["tables", "sane_lists"])
    page_html = html_path.read_text().replace("{{body}}", body_html)
    return HTML(string=page_html, base_url=str(paths.TEMPLATES_DIR)).write_pdf(
        stylesheets=[str(css_path)]
    )
