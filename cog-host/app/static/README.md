# Vendoring HTMX

The dev container this project was built in blocks outbound access to
`unpkg.com` and `cdn.jsdelivr.net` (both attempts returned `403` from the
egress proxy), so `htmx.min.js` could not be downloaded here. The app works
fully without it (plain HTML forms, full page reloads) - HTMX is a
progressive enhancement, not a requirement.

To vendor it on the Pi:

```bash
curl -sSL -o app/static/htmx.min.js https://unpkg.com/htmx.org@2.0.3/dist/htmx.min.js
```

Verify the download (check the file size looks like a real minified JS
bundle, not an HTML error page) before trusting it, and pin the version you
fetched here. `main.py` already references `/static/htmx.min.js`; the
script tag fails silently and harmlessly if the file is absent.
