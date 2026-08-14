"""Convert the annual report's Markdown text into a branded, print-ready PDF.

Mirrors the fixed Markdown structure produced by annual_communicator_agent (see
agents/annual.py) into an HTML document styled by reporting/templates/annual_report.css,
then rasterizes it to PDF bytes via WeasyPrint.
"""
from .. import paths
from ..i18n import get_language, t


def render_annual_report_pdf(report_markdown: str) -> bytes:
    """Render the annual_communicator's Markdown report as a styled PDF.

    markdown and weasyprint are imported here, not at module level: weasyprint
    pulls in native Pango/Cairo bindings, and a missing/broken system install
    should only ever break this one call, not app startup or any other endpoint.

    The HTML template's `lang`/`<title>` and the CSS's three `@page` margin-box `content:`
    strings (masthead + page-number label) are filled in from the active request's language
    (mobility_advisor.i18n.get_language()) here — WeasyPrint takes a stylesheet as a static
    file/string, so a per-language variant has to be built at render time rather than living
    in the .css file itself. See templates/annual_report.css's comment on the __TOKEN__
    placeholders this replaces.
    """
    import markdown
    from weasyprint import CSS, HTML

    html_path = paths.TEMPLATES_DIR / "annual_report.html"
    css_path = paths.TEMPLATES_DIR / "annual_report.css"

    body_html = markdown.markdown(report_markdown, extensions=["tables", "sane_lists"])
    page_html = (
        html_path.read_text()
        .replace("{{lang}}", get_language())
        .replace("{{title}}", t("report.pdf.title"))
        .replace("{{body}}", body_html)
    )
    css_text = (
        css_path.read_text()
        .replace("__MASTHEAD_LEFT__", t("report.pdf.mastheadLeft"))
        .replace("__MASTHEAD_RIGHT__", t("report.pdf.mastheadRight"))
        .replace("__PAGE_LABEL__", t("report.pdf.pageLabel"))
        .replace("__OF_LABEL__", t("report.pdf.ofLabel"))
    )
    return HTML(string=page_html, base_url=str(paths.TEMPLATES_DIR)).write_pdf(
        stylesheets=[CSS(string=css_text, base_url=str(paths.TEMPLATES_DIR))]
    )
