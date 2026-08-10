# scbrown.github.io

Personal site, served at <https://scbrown.github.io/> and intended for
`steve.brown.name` once DNS is confirmed.

Single static `index.html`, no build step and no dependencies. Edit and push.

## Pointing steve.brown.name here

1. Confirm the registrar allows A/CNAME records. `.name` third-level
   registrations were historically sold as email-forwarding products with no
   real DNS control; if that is the case here, this stays on the github.io URL.
2. Add a `CNAME` file containing `steve.brown.name`.
3. At the registrar, CNAME `steve.brown.name` to `scbrown.github.io`.
4. In repo Settings > Pages, set the custom domain and enable Enforce HTTPS.

## Deliberately not published here

The resume PDF. It carries a phone number and street address, and a public
site is a different exposure than sending it to a named recruiter.
