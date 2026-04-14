"""
conftest.py — pytest configuration for DAT Task Scraper tests.

Mocks the _tkinter C-extension so the test suite can import tkinter on
environments where the Tk shared library is not installed (e.g. CI containers).
The mock is installed into sys.modules *before* any test module imports tkinter,
which prevents the ImportError that would otherwise abort the entire session.
"""

import sys
from unittest.mock import MagicMock

# Only inject the mock when the real C extension is absent.
try:
    import _tkinter  # noqa: F401 — will raise ImportError if Tk not installed
except ImportError:
    sys.modules["_tkinter"] = MagicMock()
