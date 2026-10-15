# Caboodle documentation compatibility routes

The retained source baseline `6387d7aa` contains only the personal homepage and README, with no compatibility pages. Implementation `6be6b11` adds redirects for the 23 known Caboodle book paths. Run `sh docs/demos/caboodle-redirects/run.sh` from the checkout to inspect the actual routes and run the checks.

Replay the retained terminal recording with `scriptreplay --log-out output.log --log-timing timing.log`. [Chrome fixture results](browser-proof.txt) cover three representative routes, query and fragment retention, a fixed destination origin, and JavaScript-disabled meta refresh. The destination was intercepted by the test; this proves source behavior, not live Tambo Pages or deployment.

The personal homepage and README are unchanged. These are browser redirects (HTTP 200 HTML with script/meta refresh), not server HTTP 301 responses. Merge and publication require owner approval and coordinated cutover after Tambo Pages is live; existing Caboodle Pages stays available until inbound links are updated.
