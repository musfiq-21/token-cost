"""English vs Bangla token cost on a local Ollama model (Agentic SWE, Part 1, Assignment 2)."""
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_MODEL = "qwen2.5:3b"


def safe_console():
    """Print Bangla to any console or redirected file without crashing."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
        except (AttributeError, ValueError):
            pass
