"""Verify the actual Pages output, including every book asset and exclusions."""
from hashlib import sha256
import json
from pathlib import Path
import sys

source = Path(__file__).resolve().parents[1]
site = Path(sys.argv[1]).resolve()
manifest = json.loads((source / 'tests/tambo-book-manifest.json').read_text())
for name, expected in manifest['files'].items():
    assert sha256((site / 'tambo' / name).read_bytes()).hexdigest() == expected, name
assert (site / 'index.html').read_bytes() == (source / 'index.html').read_bytes()
assert not (site / 'tests').exists(), 'tests leaked into Pages'
assert not (site / 'docs/demos').exists(), 'demo artifacts leaked into Pages'
print(f"PASS actual Pages artifact: {len(manifest['titles'])} routes, all assets, unchanged homepage, exclusions")
