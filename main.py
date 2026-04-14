"""
main.py — Tkinter GUI entry point for the DAT Task Scraper.

Presents a minimal window with:
  - A single "Process" button that triggers HTML-to-Markdown conversion.
  - A status label that shows "✓ Success" (green) or "✗ Error: …" (red).

Usage
-----
    python main.py
    # or via Docker:
    docker compose up
"""

import os
import tkinter as tk
from tkinter import ttk

import scraper


class App:
    """Main application window for the DAT Task Scraper."""

    WINDOW_TITLE = "DAT Task Scraper"
    WINDOW_MIN_W = 380
    WINDOW_MIN_H = 150

    COLOR_SUCCESS = "#2e7d32"  # dark green
    COLOR_ERROR = "#c62828"    # dark red
    COLOR_IDLE = "#555555"     # neutral grey

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title(self.WINDOW_TITLE)
        self.root.resizable(True, True)
        self.root.minsize(self.WINDOW_MIN_W, self.WINDOW_MIN_H)
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = {"padx": 20, "pady": 8}

        frame = ttk.Frame(self.root, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)

        # Title label
        ttk.Label(
            frame,
            text="DAT Task Scraper",
            font=("Helvetica", 14, "bold"),
        ).pack(**outer)

        # Process button — the only interactive control
        self.btn_process = ttk.Button(
            frame,
            text="Process",
            command=self._on_process,
            width=22,
        )
        self.btn_process.pack(**outer)

        # Status label — updated after each run
        self.lbl_status = tk.Label(
            frame,
            text="Ready — place raw_task.html in the project root, then click Process.",
            fg=self.COLOR_IDLE,
            wraplength=340,
            justify=tk.LEFT,
        )
        self.lbl_status.pack(**outer)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_process(self) -> None:
        """Called when the user clicks the Process button."""
        self.btn_process.config(state=tk.DISABLED)
        self.lbl_status.config(text="Processing…", fg=self.COLOR_IDLE)
        self.root.update_idletasks()

        try:
            output_path = scraper.process(working_dir=os.getcwd())
            filename = os.path.basename(output_path)
            self.lbl_status.config(
                text=f"✓ Success — wrote {filename}",
                fg=self.COLOR_SUCCESS,
            )
        except RuntimeError as exc:
            self.lbl_status.config(
                text=f"✗ Error: {exc}",
                fg=self.COLOR_ERROR,
            )
        except Exception as exc:  # catch-all for unexpected failures
            self.lbl_status.config(
                text=f"✗ Error: {exc}",
                fg=self.COLOR_ERROR,
            )
        finally:
            self.btn_process.config(state=tk.NORMAL)

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Start the Tkinter main event loop (blocks until window is closed)."""
        self.root.mainloop()


if __name__ == "__main__":
    App().run()
