# Running Murus in production

This is how murus.net is deployed: the arena runs on a home machine, and a
Cloudflare tunnel publishes it. No ports are opened on the router and the
home IP is never exposed — `cloudflared` dials out to Cloudflare, and traffic
arrives through that connection.

## Layout

    server   uvicorn on 127.0.0.1:8000, loopback only
    tunnel   cloudflared, murus.net + www -> localhost:8000
    bot      the reference bot, connecting over the public API like any engine

The server binds loopback deliberately: the tunnel is the only way in.

## Environment

| variable | purpose |
|---|---|
| `MURUS_DB` | sqlite path; keep it outside the repository |
| `MURUS_SECURE_COOKIES=1` | mark session cookies Secure (HTTPS-only site) |
| `MURUS_TRUST_CF_IP=1` | rate-limit on `CF-Connecting-IP`, not the tunnel's address |
| `MURUS_FORCE_HTTPS=1` | redirect edge requests that arrived over http |

Run uvicorn with `--proxy-headers`. All four flags belong together: behind a
proxy, every client looks like 127.0.0.1 unless the forwarded headers are
trusted, and Secure cookies are silently dropped on plain http.

Note that `MURUS_FORCE_HTTPS` redirects only requests carrying
`X-Forwarded-Proto: http`. Direct loopback callers — a local bot, a health
check — are left alone, since redirecting them points at `https://127.0.0.1`
where nothing is listening.

## Cloudflare tunnel

    cloudflared tunnel login
    cloudflared tunnel create <name>
    cloudflared tunnel route dns <name> example.com
    cloudflared tunnel route dns <name> www.example.com

`%USERPROFILE%\.cloudflared\config.yml`:

    tunnel: <tunnel-uuid>
    credentials-file: <path to the generated .json>
    ingress:
      - hostname: example.com
        service: http://localhost:8000
      - hostname: www.example.com
        service: http://localhost:8000
      - service: http_status:404

Then `cloudflared tunnel run <name>`.

## Starting at boot

`cloudflared service install` and Windows scheduled tasks both need
administrator rights. Without them, `.cmd` launchers in the per-user Startup
folder (`shell:startup`) achieve the same thing at logon.

One PowerShell trap worth knowing: uvicorn and cloudflared log to stderr, and
PowerShell 5.1 wraps native stderr in ErrorRecords, so under
`$ErrorActionPreference = "Stop"` ordinary startup logging aborts the script.
Redirect through `cmd /c "... >> log 2>&1"` instead.

## Upgrading

The database is the only stateful thing. Stop the server, copy it with
sqlite's backup API rather than copying the file (WAL mode keeps recent
writes in a sidecar), then restart. Games interrupted by a restart are
reconciled to `aborted` at startup, with no rating change.

## The murus.net deployment, concretely

A 2 vCPU / 2 GB Hetzner box running Ubuntu, everything under a `murus`
user, three systemd units: `murus` (server), `murus-tunnel`, and
`murus-bot`. Reboot-tested end to end — the site answers again about fifty
seconds after `reboot`.

Four things were not obvious in advance:

**The distribution Python was too new.** Ubuntu 26.04 ships Python 3.14, which
has no wheels yet for numba or torch, and numba is not optional — it is the
rules engine. `uv python install 3.12` pins a known-good interpreter without
touching the system one.

**Install CPU torch explicitly.** `--index-url https://download.pytorch.org/whl/cpu`
keeps the venv near 1 GB; the default CUDA build is far larger and useless
without a GPU. Add swap before installing on a 2 GB box.

**`web/dist` is gitignored**, so a fresh clone serves the API and a placeholder
instead of the site. Either install Node on the host and build there, or build
locally and copy `web/dist` across. The server picks it up automatically.

**The bot measures its own speed.** Search throughput spans two orders of
magnitude between a discrete GPU (~22k simulations a second) and a shared
vCPU (~300), so the bot calibrates at startup rather than trusting a constant.
On this host that is about 1,500 simulations per move at a 6 second budget.
Give it both cores (`OMP_NUM_THREADS=2`) with `Nice=5` so the server still
wins any contention.

Hardening is ufw with SSH only — the tunnel is outbound, so nothing else needs
to be reachable — plus key-only SSH and unattended upgrades. `ss -tlnp` should
show the arena bound to `127.0.0.1:8000` and nothing else public.

## SSH access

The server is reached as a named, non-root account:

    ssh -i <deploy-key> steven@<host>

Root login over SSH is closed (`PermitRootLogin no`), password and
keyboard-interactive authentication are off, and `AllowUsers` names the single
admin account, so a stolen key lands on an auditable account rather than
directly on uid 0. `MaxAuthTries 3` with a 20-second grace, fail2ban banning
for an hour after four failures, and agent/TCP/X11 forwarding all disabled —
nothing in this deployment needs to forward anything, and a compromised
session should not be able to relay through the box or reach services bound to
loopback.

Port 22 stays open to the internet. With passwords off that is a scanner
knocking on a door with no handle, and closing it to a single residential IP
trades a small risk for a real chance of locking yourself out when the address
changes.

The deploy key should carry a passphrase, loaded into an agent for the session
rather than left bare on disk:

    ssh-keygen -p -f <deploy-key>     # set it, interactively, once
    ssh-add <deploy-key>              # per session (or persistent on Windows)

That protects the key at rest — backups, cloud sync, another account on the
machine — which is the threat that matters, since anyone already inside a
logged-in desktop session can use a loaded agent regardless.
