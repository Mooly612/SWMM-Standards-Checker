"""Cross-platform console entry point.

Two modes:
  swmm-compliance                 → launch the local web GUI (opens in browser)
  swmm-compliance check FILE      → run a check in the terminal, print JSON
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def _launch_gui() -> int:
    """Start Streamlit on localhost and open the default browser. Works on Win/macOS/Linux."""
    from streamlit.web import cli as stcli

    app = Path(__file__).with_name("app.py")
    sys.argv = ["streamlit", "run", str(app),
                "--server.address", "localhost",
                "--browser.gatherUsageStats", "false"]
    return stcli.main()  # blocks, serves http://localhost:8501


def main() -> int:
    args = sys.argv[1:]
    if args and args[0] == "check":
        if len(args) < 2:
            print("usage: swmm-compliance check <file.json|file.inp> [pipe_class]", file=sys.stderr)
            return 2
        from .checker import check_file
        pipe_class = args[2] if len(args) > 2 else "stormwater"
        result = check_file(args[1], pipe_class=pipe_class, use_llm="--no-llm" not in args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if not result["findings"] else 1
    return _launch_gui()


if __name__ == "__main__":
    sys.exit(main())
