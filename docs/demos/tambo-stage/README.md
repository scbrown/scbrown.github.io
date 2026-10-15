# Canonical book staging proof

Before: all 23 canonical Tambo book routes returned HTTP 404 while the legacy
introduction returned HTTP 200. This source overlay supplies the same book
built from the reviewed project commit, with an exact file manifest.

Replay the local source controls with `python3 -m unittest discover -s tests -p test_tambo_stage.py -v`.
`output.log` and `timing.log` record that run. It checks 23 route bodies, local
assets, source-build hashes, and unchanged personal homepage/README bytes.
The CI job separately builds the actual Pages artifact and checks every book
file and the exclusion of tests and this demo. Live route acceptance remains
pending publication; this is not a claim that the site already serves Tambo.
