"""Inspect the actual Pages build, including positive routes and exclusions."""
import json
from pathlib import Path
import sys

source = Path(__file__).resolve().parents[1]
site = Path(sys.argv[1]).resolve()
routes = json.loads((source / "tests/legacy-book-paths.json").read_text())
for name in routes:
    path = site / "caboodle" / name
    assert path.is_file(), f"missing published compatibility route: {name}"
    assert path.read_bytes() == (source / "caboodle" / name).read_bytes(), name
assert (site / "index.html").read_bytes() == (source / "index.html").read_bytes()
assert not (site / "tests").exists(), "tests leaked into Pages output"
assert not (site / "docs/demos").exists(), "demo artifacts leaked into Pages output"
print(f"PASS actual Pages artifact: {len(routes)} routes, unchanged homepage, no tests/demo artifacts")
