"""
scraper.py — Core HTML-to-Markdown conversion logic for the DAT Task Scraper.

Public API
----------
    process(working_dir: str) -> str
        Reads raw_task.html from working_dir, strips boilerplate, converts form
        fields to Markdown placeholders, runs markdownify, writes cleaned_task_N.md,
        and returns the output path.  Raises RuntimeError on any failure.
"""

import os
import re
from pathlib import Path

from bs4 import BeautifulSoup, Tag
import markdownify as md_lib


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

INPUT_FILENAME = "raw_task.html"
OUTPUT_PREFIX = "cleaned_task_"
OUTPUT_SUFFIX = ".md"

# Tags that represent navigation/chrome/boilerplate — stripped entirely.
BOILERPLATE_TAGS = {
    "nav",
    "header",
    "footer",
    "aside",
    "script",
    "style",
    "noscript",
    "iframe",
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _strip_boilerplate(soup: BeautifulSoup) -> None:
    """Remove boilerplate elements from *soup* in-place."""
    for tag_name in BOILERPLATE_TAGS:
        for element in soup.find_all(tag_name):
            element.decompose()


def _label_for(element: Tag, soup: BeautifulSoup) -> str:
    """Return the most descriptive label string for a form element."""
    # 1. Explicit <label for="..."> referencing this element's id
    elem_id = element.get("id")
    if elem_id:
        label_tag = soup.find("label", attrs={"for": elem_id})
        if label_tag:
            return label_tag.get_text(strip=True)

    # 2. Ancestor <label> wrapping this element
    parent = element.parent
    while parent and getattr(parent, "name", None) not in (None, "body", "[document]"):
        if parent.name == "label":
            return parent.get_text(strip=True)
        parent = parent.parent

    # 3. Fallbacks: common descriptive attributes
    for attr in ("aria-label", "placeholder", "name", "type"):
        val = element.get(attr)
        if val:
            return val

    return "field"


def _convert_form_fields(soup: BeautifulSoup) -> None:
    """
    Replace interactive form elements with human-readable Markdown placeholders
    so the resulting Markdown is easy for an AI agent to parse.

    Examples
    --------
        <input type="text" name="answer">  →  **Field: answer:** ___
        <select name="choice">             →  **Field: choice:** ___
        <textarea name="notes">            →  **Field: notes:** ___
        <input type="checkbox" id="q1">   →  **Checkbox: Question 1:** [ ]
        <input type="radio" name="opt">   →  **Option: opt:** ( )
    """
    for tag_name in ("input", "select", "textarea"):
        for element in soup.find_all(tag_name):
            input_type = element.get("type", "text").lower()

            # Skip non-content inputs
            if input_type in ("hidden", "submit", "button", "image", "reset"):
                element.decompose()
                continue

            label_text = _label_for(element, soup)

            if input_type == "checkbox":
                placeholder = f"**Checkbox: {label_text}:** [ ]"
            elif input_type == "radio":
                placeholder = f"**Option: {label_text}:** ( )"
            else:
                placeholder = f"**Field: {label_text}:** ___"

            new_tag = soup.new_tag("p")
            new_tag.string = placeholder
            element.replace_with(new_tag)


def _next_output_index(working_dir: Path) -> int:
    """
    Scan *working_dir* for existing ``cleaned_task_N.md`` files and return the
    next integer N.  Starts at 1 and guarantees no existing file is overwritten.
    """
    pattern = re.compile(
        r"^" + re.escape(OUTPUT_PREFIX) + r"(\d+)" + re.escape(OUTPUT_SUFFIX) + r"$"
    )
    max_index = 0
    for entry in working_dir.iterdir():
        match = pattern.match(entry.name)
        if match:
            max_index = max(max_index, int(match.group(1)))
    return max_index + 1


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def process(working_dir: str) -> str:
    """
    Main entry point for the scraper.

    Parameters
    ----------
    working_dir:
        Absolute (or relative) path to the directory that contains
        ``raw_task.html``.  Output is written to the same directory.

    Returns
    -------
    str
        Absolute path of the written Markdown file.

    Raises
    ------
    RuntimeError
        Human-readable message on any I/O or parse failure.
    """
    dir_path = Path(working_dir).resolve()
    input_path = dir_path / INPUT_FILENAME

    # --- Read input -------------------------------------------------------
    if not input_path.exists():
        raise RuntimeError(f"Input file not found: {input_path}")

    try:
        html_content = input_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise RuntimeError(f"Could not read {INPUT_FILENAME}: {exc}") from exc

    if not html_content.strip():
        raise RuntimeError(f"{INPUT_FILENAME} is empty.")

    # --- Parse & clean ----------------------------------------------------
    try:
        soup = BeautifulSoup(html_content, "lxml")
    except Exception as exc:
        raise RuntimeError(f"HTML parse error: {exc}") from exc

    _strip_boilerplate(soup)
    _convert_form_fields(soup)

    # --- Convert to Markdown ----------------------------------------------
    body = soup.find("body") or soup
    try:
        markdown_text = md_lib.markdownify(
            str(body),
            heading_style=md_lib.ATX,
            bullets="-",
            strip=["form"],   # keep form children but drop the <form> wrapper
        )
    except Exception as exc:
        raise RuntimeError(f"Markdown conversion error: {exc}") from exc

    # Collapse runs of more than 2 blank lines
    markdown_text = re.sub(r"\n{3,}", "\n\n", markdown_text).strip()

    if not markdown_text:
        raise RuntimeError(
            "No content remained after parsing. Is raw_task.html meaningful HTML?"
        )

    # --- Determine output filename ----------------------------------------
    try:
        index = _next_output_index(dir_path)
    except OSError as exc:
        raise RuntimeError(f"Could not scan output directory: {exc}") from exc

    output_filename = f"{OUTPUT_PREFIX}{index}{OUTPUT_SUFFIX}"
    output_path = dir_path / output_filename

    # --- Write output -----------------------------------------------------
    try:
        output_path.write_text(markdown_text, encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"Could not write {output_filename}: {exc}") from exc

    return str(output_path)
