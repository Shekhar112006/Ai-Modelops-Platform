"""Central version metadata for the AI ModelOps Platform."""

from pathlib import Path


VERSION_FILE = Path(__file__).resolve().with_name("VERSION")
PLATFORM_VERSION = VERSION_FILE.read_text(encoding="utf-8").strip()

if not PLATFORM_VERSION:
    raise RuntimeError("The VERSION file must not be empty.")
