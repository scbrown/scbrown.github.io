"""Staged source bytes and missing/changed artifact refusal controls."""
from pathlib import Path
import shutil
import tempfile
import unittest
from check_quechua_published import ROOT, check


class QuechuaStage(unittest.TestCase):
    def test_source(self):
        check(ROOT)

    def test_corrupted_or_missing_artifact_refuses(self):
        for name in ["ns.ttl", "ns.html"]:
            for mutation in ["missing", "changed"]:
                with self.subTest(name=name, mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                    site = Path(tmp)
                    shutil.copytree(ROOT / "quechua", site / "quechua")
                    target = site / "quechua" / name
                    if mutation == "missing":
                        target.unlink()
                    else:
                        data = target.read_bytes()
                        target.write_bytes(bytes([data[0] ^ 1]) + data[1:])
                    with self.assertRaises((FileNotFoundError, AssertionError)):
                        check(site)
