"""Show namespace artifact availability before and after, not public routing."""
import subprocess
import sys
BASE = "271d4e4bbdc9e8729eff65a60f384218976fe2db"
for name in ["quechua/ns.ttl", "quechua/ns.html", "caboodle/index.html"]:
    found = subprocess.run(["git", "cat-file", "-e", BASE + ":" + name], capture_output=True).returncode == 0
    print("BASE", name, "present=" + str(found), flush=True)
print("CANDIDATE exact legacy namespace source check:", flush=True)
subprocess.run([sys.executable, "tests/check_quechua_published.py", "."], check=True)
print("Missing and same-length-corruption controls:", flush=True)
subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_quechua_stage.py", "-v"], check=True)
