"""Check exact legacy namespace representations in source or real Pages output."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "tests/quechua-legacy-manifest.json"


def check(site):
    manifest = json.loads(MANIFEST.read_text())
    assert manifest["source_repository"] == "https://github.com/scbrown/quechua"
    assert manifest["source_commit"] == "04071d1b4340692d0b33ed5aca856dd3b994efce"
    entries = manifest["files"]
    assert [entry["published_path"] for entry in entries] == ["quechua/ns.ttl", "quechua/ns.html"]
    for entry in entries:
        data = (site / entry["published_path"]).read_bytes()
        assert len(data) == entry["bytes"], entry["published_path"]
        assert hashlib.sha256(data).hexdigest() == entry["sha256"], entry["published_path"]
    print("PASS two exact legacy namespace representations (artifact proof only)")


if __name__ == "__main__":
    check(Path(sys.argv[1]).resolve())
