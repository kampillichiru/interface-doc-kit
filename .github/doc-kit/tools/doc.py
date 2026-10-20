"""Entry point of the documentation kit tools. Run from the workspace root:

    python .github/doc-kit/tools/doc.py next
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows consoles default to cp1252

from dockit.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
