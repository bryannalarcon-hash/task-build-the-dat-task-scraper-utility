"""
test_main.py — Unit tests for main.py (Tkinter GUI entry point).

Strategy
--------
All tkinter/ttk widget classes are patched at the module level so:
  1. No display connection is required.
  2. We can verify that widget configuration calls are made with the correct
     arguments (label text, fg colour, button state).

The conftest.py in this directory already injects a _tkinter mock, which lets
`import tkinter` succeed on headless environments.  The patches here go further:
they replace Tk, ttk.Frame, ttk.Button, ttk.Label, and tk.Label with MagicMocks
so that no real widget tree is ever constructed.
"""

import os
import tkinter as tk
import pytest
from unittest.mock import MagicMock, patch, call


# ---------------------------------------------------------------------------
# Fixture — headless App instance
# ---------------------------------------------------------------------------

TK_PATCHES = [
    "tkinter.Tk",
    "tkinter.ttk.Frame",
    "tkinter.ttk.Label",
    "tkinter.ttk.Button",
    "tkinter.Label",
    "tkinter.BOTH",
    "tkinter.LEFT",
]


@pytest.fixture()
def app():
    """
    Return a fresh App instance with all Tkinter widgets mocked.

    Yields a dict with:
      app        — the App instance
      mock_root  — the mocked Tk() root window
      mock_btn   — the mocked Process button widget
      mock_label — the mocked status Label widget
    """
    with patch("tkinter.Tk") as mock_tk_cls, \
         patch("tkinter.ttk.Frame"), \
         patch("tkinter.ttk.Label"), \
         patch("tkinter.ttk.Button") as mock_btn_cls, \
         patch("tkinter.Label") as mock_lbl_cls:

        mock_root = MagicMock(name="Tk_root")
        mock_tk_cls.return_value = mock_root

        mock_btn = MagicMock(name="btn_process")
        mock_btn_cls.return_value = mock_btn

        mock_lbl = MagicMock(name="lbl_status")
        mock_lbl_cls.return_value = mock_lbl

        import main
        instance = main.App()

        yield {
            "app": instance,
            "mock_root": mock_root,
            "mock_btn": mock_btn,
            "mock_label": mock_lbl,
        }


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestAppConstruction:
    def test_window_title_set(self, app):
        app["mock_root"].title.assert_called_with("DAT Task Scraper")

    def test_process_button_attribute_exists(self, app):
        assert hasattr(app["app"], "btn_process")

    def test_status_label_attribute_exists(self, app):
        assert hasattr(app["app"], "lbl_status")

    def test_window_minsize_called(self, app):
        app["mock_root"].minsize.assert_called_once_with(
            main.App.WINDOW_MIN_W, main.App.WINDOW_MIN_H
        )

    def test_process_button_created_with_process_text(self):
        """The Process button must be labelled exactly 'Process' (AC #2)."""
        with patch("tkinter.Tk"), \
             patch("tkinter.ttk.Frame"), \
             patch("tkinter.ttk.Label"), \
             patch("tkinter.ttk.Button") as mock_btn_cls, \
             patch("tkinter.Label"):
            import main
            main.App()
            # Inspect the kwargs used to create the button
            _, kwargs = mock_btn_cls.call_args
            assert kwargs.get("text") == "Process"


# ---------------------------------------------------------------------------
# _on_process — success path
# ---------------------------------------------------------------------------


class TestOnProcessSuccess:
    def test_status_label_shows_success_text(self, app):
        with patch("scraper.process", return_value="/workspace/cleaned_task_1.md"):
            app["app"]._on_process()

        calls = app["mock_label"].config.call_args_list
        success_calls = [c for c in calls if "✓ Success" in str(c)]
        assert success_calls, "Expected a '✓ Success' config call on the label"

    def test_status_label_success_uses_green_fg(self, app):
        with patch("scraper.process", return_value="/workspace/cleaned_task_1.md"):
            app["app"]._on_process()

        # Find the final config call that sets success state
        for c in reversed(app["mock_label"].config.call_args_list):
            _, kw = c
            if "✓ Success" in kw.get("text", ""):
                assert kw["fg"] == main.App.COLOR_SUCCESS
                return
        pytest.fail("No success config call found on status label")

    def test_status_label_shows_output_filename(self, app):
        with patch("scraper.process", return_value="/workspace/cleaned_task_42.md"):
            app["app"]._on_process()

        # filename extraction: basename of the returned path
        for c in app["mock_label"].config.call_args_list:
            _, kw = c
            if "cleaned_task_42.md" in kw.get("text", ""):
                return
        pytest.fail("Output filename not shown in success status label")

    def test_button_re_enabled_after_success(self, app):
        with patch("scraper.process", return_value="/workspace/cleaned_task_1.md"):
            app["app"]._on_process()

        # The finally block must set state=NORMAL
        re_enable_calls = [
            c for c in app["mock_btn"].config.call_args_list
            if c[1].get("state") == tk.NORMAL
        ]
        assert re_enable_calls, "Button must be re-enabled after success"


# ---------------------------------------------------------------------------
# _on_process — RuntimeError path
# ---------------------------------------------------------------------------


class TestOnProcessRuntimeError:
    def test_status_label_shows_error_text(self, app):
        with patch("scraper.process", side_effect=RuntimeError("raw_task.html not found")):
            app["app"]._on_process()

        for c in app["mock_label"].config.call_args_list:
            _, kw = c
            if "✗ Error" in kw.get("text", ""):
                return
        pytest.fail("No '✗ Error' config call found on label for RuntimeError")

    def test_status_label_includes_error_message(self, app):
        err_msg = "raw_task.html not found"
        with patch("scraper.process", side_effect=RuntimeError(err_msg)):
            app["app"]._on_process()

        for c in app["mock_label"].config.call_args_list:
            _, kw = c
            if err_msg in kw.get("text", ""):
                return
        pytest.fail(f"Error message '{err_msg}' not shown in label")

    def test_status_label_error_uses_red_fg(self, app):
        with patch("scraper.process", side_effect=RuntimeError("oops")):
            app["app"]._on_process()

        for c in reversed(app["mock_label"].config.call_args_list):
            _, kw = c
            if "✗ Error" in kw.get("text", ""):
                assert kw["fg"] == main.App.COLOR_ERROR
                return
        pytest.fail("No error fg color set on label")

    def test_button_re_enabled_after_runtime_error(self, app):
        """Button must be re-enabled in the finally block even when scraper raises."""
        with patch("scraper.process", side_effect=RuntimeError("oops")):
            app["app"]._on_process()

        re_enable_calls = [
            c for c in app["mock_btn"].config.call_args_list
            if c[1].get("state") == tk.NORMAL
        ]
        assert re_enable_calls, "Button must be re-enabled after RuntimeError"


# ---------------------------------------------------------------------------
# _on_process — unexpected exception path (catch-all)
# ---------------------------------------------------------------------------


class TestOnProcessUnexpectedError:
    def test_unexpected_exception_shown_as_error(self, app):
        with patch("scraper.process", side_effect=OSError("disk full")):
            app["app"]._on_process()

        for c in app["mock_label"].config.call_args_list:
            _, kw = c
            if "✗ Error" in kw.get("text", "") and "disk full" in kw.get("text", ""):
                return
        pytest.fail("Unexpected OSError not surfaced in label")

    def test_button_re_enabled_after_unexpected_error(self, app):
        with patch("scraper.process", side_effect=OSError("disk full")):
            app["app"]._on_process()

        re_enable_calls = [
            c for c in app["mock_btn"].config.call_args_list
            if c[1].get("state") == tk.NORMAL
        ]
        assert re_enable_calls, "Button must be re-enabled after unexpected error"

    def test_keyboard_interrupt_not_swallowed(self, app):
        """KeyboardInterrupt should NOT be caught by the catch-all handler."""
        with patch("scraper.process", side_effect=KeyboardInterrupt):
            with pytest.raises(KeyboardInterrupt):
                app["app"]._on_process()


# ---------------------------------------------------------------------------
# _on_process — button disable/re-enable sequencing
# ---------------------------------------------------------------------------


class TestButtonStateSequencing:
    def test_button_disabled_before_success_then_reenabled(self, app):
        """
        Verify the disable→(work)→re-enable sequence.
        The button config call with DISABLED must precede the one with NORMAL.
        """
        state_sequence = []

        def capture(**kwargs):
            if "state" in kwargs:
                state_sequence.append(kwargs["state"])

        app["mock_btn"].config.side_effect = capture

        with patch("scraper.process", return_value="/workspace/cleaned_task_1.md"):
            app["app"]._on_process()

        assert tk.DISABLED in state_sequence, "Button must be disabled during processing"
        assert tk.NORMAL in state_sequence, "Button must be re-enabled after processing"
        disabled_idx = next(i for i, s in enumerate(state_sequence) if s == tk.DISABLED)
        normal_idx = next(i for i, s in enumerate(reversed(state_sequence)) if s == tk.NORMAL)
        # DISABLED appears before NORMAL in the sequence
        assert disabled_idx < (len(state_sequence) - normal_idx)

    def test_button_disabled_before_error_then_reenabled(self, app):
        state_sequence = []

        def capture(**kwargs):
            if "state" in kwargs:
                state_sequence.append(kwargs["state"])

        app["mock_btn"].config.side_effect = capture

        with patch("scraper.process", side_effect=RuntimeError("fail")):
            app["app"]._on_process()

        assert tk.DISABLED in state_sequence
        assert tk.NORMAL in state_sequence


# ---------------------------------------------------------------------------
# App.run
# ---------------------------------------------------------------------------


class TestAppRun:
    def test_run_calls_mainloop(self, app):
        app["app"].run()
        app["mock_root"].mainloop.assert_called_once()


# ---------------------------------------------------------------------------
# Module-level import guard
# ---------------------------------------------------------------------------


class TestModuleGuard:
    def test_importing_main_does_not_start_gui(self):
        """
        Importing main.py must not call Tk() unconditionally — only App() should.
        This test re-imports the module (if possible) and verifies no side effects.
        """
        import importlib
        import sys

        with patch("tkinter.Tk") as mock_tk, \
             patch("tkinter.ttk.Frame"), \
             patch("tkinter.ttk.Label"), \
             patch("tkinter.ttk.Button"), \
             patch("tkinter.Label"):
            # Remove cached module so we get a fresh import
            sys.modules.pop("main", None)
            importlib.import_module("main")
            # Importing alone must NOT have called Tk()
            mock_tk.assert_not_called()


# Need to import main for the constant comparisons
import main  # noqa: E402
