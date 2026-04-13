"""
test_scraper.py — Unit and integration tests for scraper.py.

Coverage targets:
  - _strip_boilerplate: all BOILERPLATE_TAGS, multiple instances, nested tags
  - _label_for: all four resolution paths + fallback
  - _convert_form_fields: every field type, skipped types, label wiring
  - _next_output_index: empty dir, one file, gaps, non-matching files
  - process (public API): happy paths, error paths, auto-increment, output content
"""

import os
import re
import pytest
from pathlib import Path
from bs4 import BeautifulSoup

import scraper
from scraper import (
    _strip_boilerplate,
    _label_for,
    _convert_form_fields,
    _next_output_index,
    process,
    BOILERPLATE_TAGS,
    INPUT_FILENAME,
    OUTPUT_PREFIX,
    OUTPUT_SUFFIX,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


# ---------------------------------------------------------------------------
# _strip_boilerplate
# ---------------------------------------------------------------------------


class TestStripBoilerplate:
    def test_removes_nav(self):
        soup = make_soup("<nav>Menu</nav><p>Content</p>")
        _strip_boilerplate(soup)
        assert soup.find("nav") is None
        assert soup.find("p") is not None

    def test_removes_header(self):
        soup = make_soup("<header>Site header</header><p>Content</p>")
        _strip_boilerplate(soup)
        assert soup.find("header") is None

    def test_removes_footer(self):
        soup = make_soup("<footer>Copyright 2024</footer><p>Content</p>")
        _strip_boilerplate(soup)
        assert soup.find("footer") is None

    def test_removes_aside(self):
        soup = make_soup("<aside>Related links</aside><p>Content</p>")
        _strip_boilerplate(soup)
        assert soup.find("aside") is None

    def test_removes_script(self):
        soup = make_soup("<script>alert('xss')</script><p>Content</p>")
        _strip_boilerplate(soup)
        assert soup.find("script") is None

    def test_removes_style(self):
        soup = make_soup("<style>.x { color: red }</style><p>Content</p>")
        _strip_boilerplate(soup)
        assert soup.find("style") is None

    def test_removes_noscript(self):
        soup = make_soup("<noscript>Enable JavaScript</noscript><p>Content</p>")
        _strip_boilerplate(soup)
        assert soup.find("noscript") is None

    def test_removes_iframe(self):
        soup = make_soup('<iframe src="ad.html"></iframe><p>Content</p>')
        _strip_boilerplate(soup)
        assert soup.find("iframe") is None

    def test_removes_all_boilerplate_tags_at_once(self):
        """All BOILERPLATE_TAGS should be stripped in a single call."""
        chunks = "".join(f"<{t}>boilerplate</{t}>" for t in BOILERPLATE_TAGS)
        soup = make_soup(chunks + "<p>Keep me</p>")
        _strip_boilerplate(soup)
        for tag_name in BOILERPLATE_TAGS:
            assert soup.find(tag_name) is None, f"<{tag_name}> should have been removed"
        assert soup.find("p") is not None

    def test_preserves_semantic_content(self):
        soup = make_soup("<h1>Title</h1><p>Para</p><ul><li>Item</li></ul>")
        _strip_boilerplate(soup)
        assert soup.find("h1") is not None
        assert soup.find("p") is not None
        assert soup.find("ul") is not None

    def test_empty_document_does_not_raise(self):
        soup = make_soup("")
        _strip_boilerplate(soup)  # must not raise

    def test_multiple_instances_of_same_tag_all_removed(self):
        soup = make_soup("<nav>Nav1</nav><p>Content</p><nav>Nav2</nav>")
        _strip_boilerplate(soup)
        assert len(soup.find_all("nav")) == 0

    def test_nested_boilerplate_children_also_removed(self):
        """Children of a boilerplate tag should disappear with their parent."""
        soup = make_soup("<nav><ul><li>Menu item</li></ul></nav><p>Content</p>")
        _strip_boilerplate(soup)
        assert soup.find("nav") is None
        assert soup.find("li") is None  # li lived inside nav, now gone too

    def test_preserves_tables(self):
        soup = make_soup("<table><tr><td>Cell</td></tr></table>")
        _strip_boilerplate(soup)
        assert soup.find("table") is not None

    def test_preserves_form_elements(self):
        soup = make_soup('<form><input type="text" name="q"></form>')
        _strip_boilerplate(soup)
        assert soup.find("input") is not None


# ---------------------------------------------------------------------------
# _label_for
# ---------------------------------------------------------------------------


class TestLabelFor:
    def test_explicit_label_for_id_wins(self):
        soup = make_soup('<label for="q1">Your name</label><input id="q1">')
        element = soup.find("input")
        assert _label_for(element, soup) == "Your name"

    def test_ancestor_label_is_used_when_no_explicit_for(self):
        soup = make_soup("<label>Email address <input type='email'></label>")
        element = soup.find("input")
        result = _label_for(element, soup)
        assert "Email" in result

    def test_aria_label_fallback(self):
        soup = make_soup('<input aria-label="Search query">')
        element = soup.find("input")
        assert _label_for(element, soup) == "Search query"

    def test_placeholder_fallback(self):
        soup = make_soup('<input placeholder="Enter your email">')
        element = soup.find("input")
        assert _label_for(element, soup) == "Enter your email"

    def test_name_attribute_fallback(self):
        soup = make_soup('<input name="username">')
        element = soup.find("input")
        assert _label_for(element, soup) == "username"

    def test_type_attribute_fallback(self):
        soup = make_soup('<input type="email">')
        element = soup.find("input")
        # No id/ancestor label/aria-label/placeholder/name — falls through to "type"
        assert _label_for(element, soup) == "email"

    def test_ultimate_fallback_is_field(self):
        soup = make_soup("<input>")
        element = soup.find("input")
        # Plain <input> with no attributes; the only attribute lxml may add is none
        # It should return "field" or "text" (if parser injects type="text")
        result = _label_for(element, soup)
        assert result in ("field", "text")

    def test_explicit_label_takes_priority_over_ancestor(self):
        soup = make_soup(
            '<label>Outer label <input id="x" aria-label="aria_label"></label>'
            '<label for="x">Explicit Label</label>'
        )
        element = soup.find("input")
        result = _label_for(element, soup)
        assert result == "Explicit Label"

    def test_select_element_label(self):
        soup = make_soup(
            '<label for="sel">Choose one</label>'
            '<select id="sel"><option>A</option></select>'
        )
        element = soup.find("select")
        assert _label_for(element, soup) == "Choose one"

    def test_textarea_element_label(self):
        soup = make_soup(
            '<label for="ta">Notes</label><textarea id="ta"></textarea>'
        )
        element = soup.find("textarea")
        assert _label_for(element, soup) == "Notes"

    def test_aria_label_takes_priority_over_placeholder(self):
        soup = make_soup('<input aria-label="ARIA" placeholder="PLACEHOLDER">')
        element = soup.find("input")
        assert _label_for(element, soup) == "ARIA"

    def test_placeholder_takes_priority_over_name(self):
        soup = make_soup('<input placeholder="PLACEHOLDER" name="NAME">')
        element = soup.find("input")
        assert _label_for(element, soup) == "PLACEHOLDER"


# ---------------------------------------------------------------------------
# _convert_form_fields
# ---------------------------------------------------------------------------


class TestConvertFormFields:
    def test_text_input_becomes_field_placeholder(self):
        soup = make_soup('<input type="text" name="answer">')
        _convert_form_fields(soup)
        assert "**Field: answer:** ___" in soup.get_text()

    def test_select_becomes_field_placeholder(self):
        soup = make_soup('<select name="choice"><option>A</option></select>')
        _convert_form_fields(soup)
        assert "**Field: choice:** ___" in soup.get_text()

    def test_textarea_becomes_field_placeholder(self):
        soup = make_soup('<textarea name="notes"></textarea>')
        _convert_form_fields(soup)
        assert "**Field: notes:** ___" in soup.get_text()

    def test_checkbox_becomes_checkbox_placeholder(self):
        soup = make_soup('<input type="checkbox" name="agree">')
        _convert_form_fields(soup)
        assert "**Checkbox: agree:** [ ]" in soup.get_text()

    def test_radio_becomes_option_placeholder(self):
        soup = make_soup('<input type="radio" name="choice">')
        _convert_form_fields(soup)
        assert "**Option: choice:** ( )" in soup.get_text()

    def test_hidden_input_is_decomposed(self):
        """Hidden inputs carry no user-visible content and must be silently removed."""
        soup = make_soup('<input type="hidden" name="csrf" value="token">')
        _convert_form_fields(soup)
        assert soup.find("input") is None
        assert "Field" not in soup.get_text()

    def test_submit_input_is_decomposed(self):
        soup = make_soup('<input type="submit" value="Submit">')
        _convert_form_fields(soup)
        assert soup.find("input") is None

    def test_button_input_is_decomposed(self):
        soup = make_soup('<input type="button" value="Click me">')
        _convert_form_fields(soup)
        assert soup.find("input") is None

    def test_image_input_is_decomposed(self):
        soup = make_soup('<input type="image" src="submit.png">')
        _convert_form_fields(soup)
        assert soup.find("input") is None

    def test_reset_input_is_decomposed(self):
        soup = make_soup('<input type="reset" value="Reset">')
        _convert_form_fields(soup)
        assert soup.find("input") is None

    def test_input_without_type_treated_as_text(self):
        """<input> with no type attribute defaults to text behaviour."""
        soup = make_soup('<input name="bare">')
        _convert_form_fields(soup)
        text = soup.get_text()
        assert "**Field: bare:** ___" in text

    def test_labeled_checkbox_uses_label_text(self):
        soup = make_soup(
            '<label for="cb1">Agree to terms</label>'
            '<input type="checkbox" id="cb1">'
        )
        _convert_form_fields(soup)
        assert "**Checkbox: Agree to terms:** [ ]" in soup.get_text()

    def test_multiple_fields_all_converted(self):
        soup = make_soup(
            '<input type="text" name="q1">'
            '<input type="text" name="q2">'
            '<input type="checkbox" name="q3">'
        )
        _convert_form_fields(soup)
        text = soup.get_text()
        assert "q1" in text
        assert "q2" in text
        assert "q3" in text

    def test_original_input_tags_replaced_by_p_tags(self):
        soup = make_soup('<input type="text" name="answer">')
        _convert_form_fields(soup)
        assert soup.find("input") is None
        assert soup.find("p") is not None

    def test_select_element_replaced(self):
        soup = make_soup('<select name="choice"><option>A</option></select>')
        _convert_form_fields(soup)
        assert soup.find("select") is None
        assert soup.find("p") is not None

    def test_textarea_element_replaced(self):
        soup = make_soup('<textarea name="notes">Existing text</textarea>')
        _convert_form_fields(soup)
        assert soup.find("textarea") is None

    def test_mixed_skipped_and_converted_fields(self):
        """Non-content inputs removed; content inputs converted."""
        soup = make_soup(
            '<input type="hidden" name="h">'
            '<input type="text" name="visible">'
            '<input type="submit" value="Go">'
        )
        _convert_form_fields(soup)
        text = soup.get_text()
        assert "visible" in text
        assert "**Field: visible:** ___" in text
        # Hidden and submit should not appear
        assert "**Field: h:** ___" not in text


# ---------------------------------------------------------------------------
# _next_output_index
# ---------------------------------------------------------------------------


class TestNextOutputIndex:
    def test_returns_1_when_directory_empty(self, tmp_path):
        assert _next_output_index(tmp_path) == 1

    def test_returns_2_when_file_1_exists(self, tmp_path):
        (tmp_path / f"{OUTPUT_PREFIX}1{OUTPUT_SUFFIX}").write_text("x")
        assert _next_output_index(tmp_path) == 2

    def test_returns_next_after_highest_contiguous(self, tmp_path):
        for i in range(1, 4):
            (tmp_path / f"{OUTPUT_PREFIX}{i}{OUTPUT_SUFFIX}").write_text("x")
        assert _next_output_index(tmp_path) == 4

    def test_handles_non_contiguous_indices(self, tmp_path):
        """Gaps in the sequence must not lower the next index."""
        (tmp_path / f"{OUTPUT_PREFIX}1{OUTPUT_SUFFIX}").write_text("x")
        (tmp_path / f"{OUTPUT_PREFIX}5{OUTPUT_SUFFIX}").write_text("x")
        assert _next_output_index(tmp_path) == 6

    def test_ignores_non_numeric_suffix(self, tmp_path):
        (tmp_path / f"{OUTPUT_PREFIX}abc{OUTPUT_SUFFIX}").write_text("x")
        assert _next_output_index(tmp_path) == 1

    def test_ignores_wrong_extension(self, tmp_path):
        (tmp_path / f"{OUTPUT_PREFIX}1.txt").write_text("x")
        assert _next_output_index(tmp_path) == 1

    def test_ignores_unrelated_md_files(self, tmp_path):
        (tmp_path / "raw_task.md").write_text("x")
        (tmp_path / "notes.md").write_text("x")
        assert _next_output_index(tmp_path) == 1

    def test_handles_large_existing_index(self, tmp_path):
        (tmp_path / f"{OUTPUT_PREFIX}99{OUTPUT_SUFFIX}").write_text("x")
        assert _next_output_index(tmp_path) == 100

    def test_zero_padded_filename_parsed_correctly(self, tmp_path):
        """'cleaned_task_01.md' → int 1, so next should be 2."""
        (tmp_path / f"{OUTPUT_PREFIX}01{OUTPUT_SUFFIX}").write_text("x")
        assert _next_output_index(tmp_path) == 2


# ---------------------------------------------------------------------------
# process — public API (integration-style tests using tmp_path)
# ---------------------------------------------------------------------------


class TestProcess:
    # --- Error cases --------------------------------------------------------

    def test_raises_runtime_error_when_input_missing(self, tmp_path):
        with pytest.raises(RuntimeError, match="not found"):
            process(str(tmp_path))

    def test_raises_runtime_error_for_empty_file(self, tmp_path):
        (tmp_path / INPUT_FILENAME).write_text("")
        with pytest.raises(RuntimeError, match="empty"):
            process(str(tmp_path))

    def test_raises_runtime_error_for_whitespace_only_file(self, tmp_path):
        """A file containing only whitespace is functionally empty."""
        (tmp_path / INPUT_FILENAME).write_text("   \n\t  \r\n  ")
        with pytest.raises(RuntimeError, match="empty"):
            process(str(tmp_path))

    def test_raises_runtime_error_for_all_boilerplate_html(self, tmp_path):
        """HTML consisting entirely of boilerplate leaves no Markdown content."""
        (tmp_path / INPUT_FILENAME).write_text(
            "<html><body>"
            "<nav>Site nav</nav>"
            "<header>Page header</header>"
            "<footer>Page footer</footer>"
            "</body></html>"
        )
        with pytest.raises(RuntimeError, match="No content"):
            process(str(tmp_path))

    # --- Happy path — return value & file creation -------------------------

    def test_returns_absolute_path_string(self, tmp_path):
        (tmp_path / INPUT_FILENAME).write_text(
            "<html><body><h1>Task</h1><p>Answer this.</p></body></html>"
        )
        result = process(str(tmp_path))
        assert isinstance(result, str)
        assert os.path.isabs(result)

    def test_first_run_creates_cleaned_task_1(self, tmp_path):
        (tmp_path / INPUT_FILENAME).write_text(
            "<html><body><h1>Task</h1><p>Answer this.</p></body></html>"
        )
        result = process(str(tmp_path))
        assert result == str(tmp_path / f"{OUTPUT_PREFIX}1{OUTPUT_SUFFIX}")
        assert Path(result).exists()

    def test_output_file_contains_task_content(self, tmp_path):
        (tmp_path / INPUT_FILENAME).write_text(
            "<html><body>"
            "<h1>Task Title</h1>"
            "<p>Please answer the following question.</p>"
            "</body></html>"
        )
        content = Path(process(str(tmp_path))).read_text()
        assert "Task Title" in content
        assert "Please answer" in content

    # --- Boilerplate stripping ---------------------------------------------

    def test_output_strips_nav(self, tmp_path):
        (tmp_path / INPUT_FILENAME).write_text(
            "<html><body>"
            "<nav>Navigation Menu</nav>"
            "<h1>Real Task</h1>"
            "<p>Do this.</p>"
            "</body></html>"
        )
        content = Path(process(str(tmp_path))).read_text()
        assert "Navigation Menu" not in content
        assert "Real Task" in content

    def test_output_strips_footer(self, tmp_path):
        (tmp_path / INPUT_FILENAME).write_text(
            "<html><body>"
            "<h1>Task</h1><p>Content</p>"
            "<footer>Footer Content</footer>"
            "</body></html>"
        )
        content = Path(process(str(tmp_path))).read_text()
        assert "Footer Content" not in content

    def test_output_strips_script_tags(self, tmp_path):
        (tmp_path / INPUT_FILENAME).write_text(
            "<html><body>"
            "<script>var x = 1;</script>"
            "<h1>Task</h1><p>Content</p>"
            "</body></html>"
        )
        content = Path(process(str(tmp_path))).read_text()
        assert "var x" not in content

    # --- Form field conversion ----------------------------------------------

    def test_text_input_converted_to_field_placeholder(self, tmp_path):
        r"""
        markdownify escapes special Markdown chars inside text nodes, so
        '**Field: full_name:** ___' becomes '\*\*Field: full\_name:\*\* \_\_\_'
        in the file.  We check for the marker prefix and the field name.
        """
        (tmp_path / INPUT_FILENAME).write_text(
            "<html><body>"
            "<p>Q1: What is your name?</p>"
            '<input type="text" name="full_name">'
            "</body></html>"
        )
        content = Path(process(str(tmp_path))).read_text()
        # markdownify escapes * → \* and _ → \_
        assert r"\*\*Field: full\_name:\*\*" in content

    def test_checkbox_converted_to_checkbox_placeholder(self, tmp_path):
        """The Checkbox marker is present in the output (escaped by markdownify)."""
        (tmp_path / INPUT_FILENAME).write_text(
            "<html><body>"
            '<label for="agree">I agree</label>'
            '<input type="checkbox" id="agree">'
            "</body></html>"
        )
        content = Path(process(str(tmp_path))).read_text()
        assert r"\*\*Checkbox: I agree:\*\*" in content
        assert "[ ]" in content

    def test_radio_converted_to_option_placeholder(self, tmp_path):
        """The Option marker is present in the output (escaped by markdownify)."""
        (tmp_path / INPUT_FILENAME).write_text(
            "<html><body>"
            '<input type="radio" name="answer" value="yes">'
            "</body></html>"
        )
        content = Path(process(str(tmp_path))).read_text()
        assert r"\*\*Option: answer:\*\*" in content
        assert "( )" in content

    def test_submit_button_not_in_output(self, tmp_path):
        (tmp_path / INPUT_FILENAME).write_text(
            "<html><body>"
            "<p>Question</p>"
            '<input type="text" name="resp">'
            '<input type="submit" value="Submit">'
            "</body></html>"
        )
        content = Path(process(str(tmp_path))).read_text()
        assert "Submit" not in content

    # --- Auto-increment & overwrite prevention -----------------------------

    def test_second_run_creates_cleaned_task_2(self, tmp_path):
        html = "<html><body><p>Content</p></body></html>"
        (tmp_path / INPUT_FILENAME).write_text(html)
        process(str(tmp_path))
        path2 = process(str(tmp_path))
        assert path2.endswith(f"{OUTPUT_PREFIX}2{OUTPUT_SUFFIX}")

    def test_successive_runs_do_not_overwrite(self, tmp_path):
        (tmp_path / INPUT_FILENAME).write_text(
            "<html><body><p>First run content</p></body></html>"
        )
        path1 = process(str(tmp_path))
        content1 = Path(path1).read_text()

        (tmp_path / INPUT_FILENAME).write_text(
            "<html><body><p>Second run content</p></body></html>"
        )
        path2 = process(str(tmp_path))

        assert path1 != path2
        assert Path(path1).read_text() == content1  # first file untouched

    def test_five_consecutive_runs_increment_correctly(self, tmp_path):
        for i in range(1, 6):
            (tmp_path / INPUT_FILENAME).write_text(
                f"<html><body><p>Run {i} content</p></body></html>"
            )
            path = process(str(tmp_path))
            assert path.endswith(f"{OUTPUT_PREFIX}{i}{OUTPUT_SUFFIX}")

    def test_existing_files_respected_on_first_call(self, tmp_path):
        """If cleaned_task_3.md already exists before first call, start at 4."""
        (tmp_path / f"{OUTPUT_PREFIX}3{OUTPUT_SUFFIX}").write_text("pre-existing")
        (tmp_path / INPUT_FILENAME).write_text(
            "<html><body><p>Content</p></body></html>"
        )
        path = process(str(tmp_path))
        assert path.endswith(f"{OUTPUT_PREFIX}4{OUTPUT_SUFFIX}")

    # --- Output format -----------------------------------------------------

    def test_output_uses_atx_headings(self, tmp_path):
        (tmp_path / INPUT_FILENAME).write_text(
            "<html><body>"
            "<h1>Heading One</h1>"
            "<h2>Heading Two</h2>"
            "</body></html>"
        )
        content = Path(process(str(tmp_path))).read_text()
        assert "# Heading One" in content
        assert "## Heading Two" in content

    def test_output_has_no_excessive_blank_lines(self, tmp_path):
        """More than two consecutive newlines must not appear in output."""
        (tmp_path / INPUT_FILENAME).write_text(
            "<html><body><p>A</p><p>B</p><p>C</p></body></html>"
        )
        content = Path(process(str(tmp_path))).read_text()
        assert "\n\n\n" not in content

    def test_output_written_to_correct_directory(self, tmp_path):
        (tmp_path / INPUT_FILENAME).write_text(
            "<html><body><p>Content</p></body></html>"
        )
        result = process(str(tmp_path))
        assert os.path.dirname(result) == str(tmp_path)

    def test_output_is_valid_utf8(self, tmp_path):
        """Non-ASCII characters in the source HTML should survive in the output."""
        (tmp_path / INPUT_FILENAME).write_text(
            "<html><body><p>Café au lait — résumé</p></body></html>",
            encoding="utf-8",
        )
        content = Path(process(str(tmp_path))).read_text(encoding="utf-8")
        assert "Café" in content

    def test_list_items_preserved(self, tmp_path):
        (tmp_path / INPUT_FILENAME).write_text(
            "<html><body>"
            "<ul><li>Item one</li><li>Item two</li></ul>"
            "</body></html>"
        )
        content = Path(process(str(tmp_path))).read_text()
        assert "Item one" in content
        assert "Item two" in content

    def test_complex_task_html(self, tmp_path):
        """End-to-end test simulating a realistic task HTML structure."""
        html = """
        <html>
        <head><title>Task</title></head>
        <body>
          <nav><ul><li><a href="/">Home</a></li></ul></nav>
          <header><h1>Site Header</h1></header>

          <main>
            <h1>Data Entry Task</h1>
            <p>Please fill in the following fields carefully.</p>

            <h2>Section A</h2>
            <label for="name">Full Name</label>
            <input type="text" id="name" name="name">

            <label for="dob">Date of Birth</label>
            <input type="text" id="dob" name="dob">

            <h2>Section B</h2>
            <p>Select all that apply:</p>
            <label><input type="checkbox" name="opt1"> Option 1</label>
            <label><input type="checkbox" name="opt2"> Option 2</label>

            <textarea name="comments" placeholder="Additional comments"></textarea>

            <input type="hidden" name="task_id" value="12345">
            <input type="submit" value="Submit">
          </main>

          <footer><p>Copyright 2024</p></footer>
          <script>console.log('tracking');</script>
        </body>
        </html>
        """
        (tmp_path / INPUT_FILENAME).write_text(html)
        content = Path(process(str(tmp_path))).read_text()

        # Boilerplate gone
        assert "Site Header" not in content
        assert "Copyright 2024" not in content
        assert "console.log" not in content

        # Task content preserved
        assert "Data Entry Task" in content
        assert "Section A" in content
        assert "Full Name" in content
        # markdownify escapes * and _ inside text nodes, so the placeholder
        # markers appear in their backslash-escaped form
        assert r"\*\*Field: Full Name:\*\*" in content
        assert r"\*\*Field: Date of Birth:\*\*" in content
        assert r"\*\*Checkbox:" in content
        assert "Additional comments" in content

        # Non-content inputs stripped
        assert "Submit" not in content
        assert "task_id" not in content
