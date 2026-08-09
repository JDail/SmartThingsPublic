"""Renders a Recommendation into a standalone HTML report."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .models import ShoppingItem
from .optimizer import Recommendation

TEMPLATE_DIR = Path(__file__).parent / "templates"


def render_report(
    shopping_list: list[ShoppingItem],
    recommendation: Recommendation,
    output_path: Path,
    run_date: date | None = None,
) -> Path:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template("report.html.j2")
    html = template.render(
        shopping_list=shopping_list,
        recommendation=recommendation,
        run_date=(run_date or date.today()).isoformat(),
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Explicit encoding - Path.write_text() defaults to the OS locale encoding
    # (cp1252 on Windows), which mangles £ even though the HTML declares utf-8.
    output_path.write_text(html, encoding="utf-8")
    return output_path
