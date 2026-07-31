# Running Palisade in production

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
| `PALISADE_DB` | sqlite path; keep it outside the repository |
| `PALISADE_SECURE_COOKIES=1` | mark session cookies Secure (HTTPS-only site) |
| `PALISADE_TRUST_CF_IP=1` | rate-limit on `CF-Connecting-IP`, not the tunnel's address |
| `PALISADE_FORCE_HTTPS=1` | redirect edge requests that arrived over http |

Run uvicorn with `--proxy-headers`. All four flags belong together: behind a
proxy, every client looks like 127.0.0.1 unless the forwarded headers are
trusted, and Secure cookies are silently dropped on plain http.

Note that `PALISADE_FORCE_HTTPS` redirects only requests carrying
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
