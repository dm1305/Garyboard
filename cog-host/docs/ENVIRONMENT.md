# Environment audit

## Where this was built

This codebase was built and tested in a cloud development container, **not**
on the Raspberry Pi 500 the plan targets. Audit run here on 19 September 2026:

```
$ cat /etc/os-release
PRETTY_NAME="Ubuntu 24.04.4 LTS"
ID=ubuntu / ID_LIKE=debian
$ uname -m
x86_64
$ python3 --version
Python 3.11.15
$ docker --version
Docker version 29.3.1
$ systemctl --user is-system-running
offline
```

This does **not** match Phase 0's expectation (Raspberry Pi OS / Debian
Bookworm, `aarch64`). It's Ubuntu 24.04 (Debian-based, so `apt`/`pipx`
workflows translate directly) on `x86_64`, and the user systemd manager is
not running here (containers usually don't run one).

## What that means for this build

- **Portable code** (everything under `app/`, `tests/`, `scripts/*.py`):
  built and tested here. Runs unmodified on the Pi - it's pure Python with
  no architecture-specific dependencies.
- **Hardware/OS-specific steps** could not be executed in this container and
  still need doing on the actual Pi:
  - Phase 0's audit (re-run the commands above on the Pi itself and record
    the real results here).
  - Phase 1's `apt install` list - not run here since this container's
    package set already differs from a fresh Pi OS image.
  - PhoneInfoga's `linux/arm64` release binary (this container is
    `x86_64` - the arm64 binary won't run here at all).
  - The systemd **user** service in `docs/cog-host.service` - drafted but
    never started, because no user systemd manager is running here.
  - The desktop launcher (`docs/cog-host.desktop`) - needs Chromium on the
    Pi to confirm the binary name (`chromium` vs `chromium-browser`).
- **Network egress**: this container's outbound network policy blocks most
  third-party hosts (confirmed while building: `unpkg.com` and
  `cdn.jsdelivr.net` were both rejected, so HTMX could not be vendored here -
  see `app/static/README.md`). Expect some API modules that worked here
  (offline checks) or failed only because of that policy (Gravatar,
  XposedOrNot, GitHub each returned `403` from the proxy during testing, not
  from the real service) to behave differently once running from the Pi's
  own network.

**Before relying on this for real searches**, re-run Phase 0's audit on the
Pi itself and update this file, then work through Phase 1 there.
