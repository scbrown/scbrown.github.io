# Legacy namespace fallback artifact

At base `271d4e4bbdc9e8729eff65a60f384218976fe2db` the two Quechua namespace routes are absent from this source tree, while the existing Caboodle route is present. Implementation `5ae51b6` stages both exact legacy representations, with missing and same-length corruption controls. The fixture is a source checkout; this does not demonstrate public routing. The current project Pages site shadows these paths until transfer. CI separately checks the actual Jekyll artifact.

Run `python3 docs/demos/quechua-namespace/reproduce.py` from the repository root. The [actual transcript](output.log) and [timing](timing.log) are retained here under the existing demo convention. Download both and use `scriptreplay --log-out output.log --log-timing timing.log`, or read the transcript. No transfer, store write or runtime activation occurs.
