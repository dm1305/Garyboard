# PhoneInfoga v2 setup (Phase 2)

Not installed or run in this dev container (this container is `x86_64`;
PhoneInfoga's official release binary you want is `linux/arm64` for the Pi).
Steps for the Pi:

1. Download the `linux/arm64` release from the official PhoneInfoga GitHub
   releases page. Verify the GPG signature before running it.
2. Run it as a local-only service:
   ```bash
   phoneinfoga serve --no-client -p 5000
   ```
   Confirm it's bound to `127.0.0.1` only (check with `ss -tlnp | grep 5000`).
3. Before wiring up more scanners than `app/modules/phoneinfoga_mod.py`
   already uses, read the live Swagger spec and list what's available:
   ```bash
   curl http://127.0.0.1:5000/api/v2/scanners
   ```
4. This project only enables the scanners that need no key: `local`, `ovh`,
   and `googlesearch` (which just generates search links). Do **not** enable
   `numverify` (free plan reported HTTP-only) or `googlecse` (Google's
   Custom Search JSON API is closed to new customers) - re-check both
   before changing this, since free-tier terms shift.
5. `app/modules/phoneinfoga_mod.py` calls `${PHONEINFOGA_URL}/api/v2/scan`
   and skips cleanly with a clear message if the service isn't reachable -
   confirmed while testing this build (no service running here, so the
   module correctly reported "PhoneInfoga not reachable").
