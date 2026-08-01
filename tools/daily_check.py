"""Daily health and activity check for murus.net, run from the operator's machine.

Runs locally rather than in the cloud for two reasons. Cloudflare challenges
requests from datacentre address ranges, so a cloud runner gets 403 where a
home connection gets 200. And a local run can reach the server over SSH, which
is the only way to see the things the public API cannot show: disk, memory,
whether the services are actually running, and what the logs have been saying.

It also keeps its own history, so it can report what CHANGED since yesterday
rather than only what exists today. Totals age badly as a signal; deltas do
not.

    python tools/daily_check.py                 # check, print, record
    python tools/daily_check.py --no-ssh        # public API only
    python tools/daily_check.py --install       # register the scheduled task
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

SITE = "https://murus.net"
HOST = "steven@5.161.76.48"
KEY = r"C:\Users\StevenPeng\palisade-run\deploy\murus_vps"
HOME = pathlib.Path.home() / "murus-checks"
SSH = r"C:\Windows\System32\OpenSSH\ssh.exe"

SLOW_SECONDS = 3.0        # above this, the site is not merely up but struggling
DISK_PERCENT = 85         # a full disk takes the site down with no warning
MEM_FREE_MB = 150         # this box has 2 GB; below this it is about to swap


def get(url: str, timeout: float = 20.0) -> tuple[int, float, dict | None]:
    """Status, seconds, parsed body. Never raises: a check that dies is a
    check that reports nothing on the day it mattered."""
    req = urllib.request.Request(url, headers={"User-Agent": "murus-daily-check"})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
            dt_s = time.perf_counter() - t0
            try:
                return r.status, dt_s, json.loads(body)
            except json.JSONDecodeError:
                return r.status, dt_s, None
    except urllib.error.HTTPError as e:
        return e.code, time.perf_counter() - t0, None
    except Exception:
        return 0, time.perf_counter() - t0, None


def ssh(cmd: str, timeout: int = 30) -> str | None:
    """One command on the server, or None if we cannot get there."""
    if not pathlib.Path(SSH).exists():
        return None
    try:
        p = subprocess.run(
            [SSH, "-i", KEY, "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
             HOST, cmd],
            capture_output=True, text=True, timeout=timeout)
        return p.stdout.strip() if p.returncode == 0 else None
    except Exception:
        return None


def server_facts() -> dict | None:
    """Disk, memory, service states and recent errors — none of which the
    public API can see, and any of which can take the site down."""
    raw = ssh(
        "df --output=pcent / | tail -1; "
        "free -m | awk '/^Mem:/{print $7}'; "
        "for s in murus murus-tunnel murus-bot; do systemctl is-active $s; done; "
        # `grep -c` prints its count and *also* exits non-zero when that count
        # is zero, so the obvious `|| echo 0` emits the number twice and shifts
        # every field after it. `|| true` keeps the count grep already printed.
        "sudo journalctl -u murus --since '24 hours ago' --no-pager 2>/dev/null "
        "| grep -ciE 'traceback|error|exception' || true; "
        "uptime -p")
    if not raw:
        return None
    lines = [l.strip() for l in raw.splitlines() if l.strip()]
    if len(lines) < 7:
        return None
    return {
        "diskPercent": int(lines[0].rstrip("%").strip()),
        "memAvailableMb": int(lines[1]),
        "services": {"murus": lines[2], "tunnel": lines[3], "bot": lines[4]},
        "errors24h": int(lines[5]),
        "uptime": lines[6],
    }


def load_history() -> list[dict]:
    f = HOME / "history.jsonl"
    if not f.exists():
        return []
    out = []
    for line in f.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue          # a truncated line is not worth losing the rest
    return out


def delta(now: int, before: int | None) -> str:
    if before is None:
        return ""
    d = now - before
    return f"  ({d:+d} since last check)" if d else ""


def report(stats: dict, health: list[tuple[str, int, float]],
           server: dict | None, prev: dict | None) -> tuple[str, list[str]]:
    """The report, and the list of things actually wrong."""
    L: list[str] = []
    alarms: list[str] = []
    u, g, r = stats["users"], stats["games"], stats["reviews"]
    on = stats.get("online", {})
    p = prev or {}
    pu, pg = p.get("users", {}), p.get("games", {})

    L.append(f"murus.net — {dt.datetime.now():%A %d %B %Y, %H:%M}")
    L.append("")

    for name, code, secs in health:
        mark = "ok  " if code == 200 and secs < SLOW_SECONDS else "FAIL"
        L.append(f"  {mark} {name:<12} {code} in {secs:.2f}s")
        if code != 200:
            alarms.append(f"{name} returned {code}")
        elif secs >= SLOW_SECONDS:
            alarms.append(f"{name} took {secs:.1f}s")

    engines = on.get("engines") or []
    L.append(f"  {'ok  ' if engines else 'FAIL'} house bot    "
             f"{', '.join(engines) if engines else 'NOT CONNECTED'}"
             f"   ({on.get('total', 0)} connected in total)")
    if not engines:
        # The failure no other number reveals: a day with no games looks the
        # same whether the bot is waiting or dead.
        alarms.append("the house bot is not connected — nobody can play it")

    if server:
        s = server["services"]
        bad = [k for k, v in s.items() if v != "active"]
        L.append(f"  {'ok  ' if not bad else 'FAIL'} services     "
                 f"{', '.join(f'{k}={v}' for k, v in s.items())}")
        if bad:
            alarms.append(f"service(s) not active: {', '.join(bad)}")
        L.append(f"  {'ok  ' if server['diskPercent'] < DISK_PERCENT else 'WARN'}"
                 f" disk         {server['diskPercent']}% used")
        if server["diskPercent"] >= DISK_PERCENT:
            alarms.append(f"disk {server['diskPercent']}% full")
        L.append(f"  {'ok  ' if server['memAvailableMb'] > MEM_FREE_MB else 'WARN'}"
                 f" memory       {server['memAvailableMb']} MB available")
        if server["memAvailableMb"] <= MEM_FREE_MB:
            alarms.append(f"only {server['memAvailableMb']} MB memory available")
        if server["errors24h"]:
            L.append(f"  WARN errors       {server['errors24h']} in the last 24h")
            alarms.append(f"{server['errors24h']} error lines in the log")
        L.append(f"       up           {server['uptime']}")
    else:
        L.append("       server       not reachable over SSH (public checks only)")

    L.append("")
    L.append("Activity")
    L.append(f"  {u['new24h']} new accounts today, {u['new7d']} this week"
             f" — {u['total']} total{delta(u['total'], pu.get('total'))}")
    L.append(f"  {g['finished24h']} games finished today, {g['finished7d']} this week"
             f" — {g['total']} total{delta(g['total'], pg.get('total'))}")
    if g["live"]:
        L.append(f"  {g['live']} game(s) in progress right now")
    if g["bySpeed"]:
        L.append("  by time control: "
                 + ", ".join(f"{k} {v}" for k, v in sorted(g["bySpeed"].items())))
    L.append(f"  {u['withRatedGames']} accounts have a rating, "
             f"{u['titled']} hold a title")

    if r["failed"]:
        alarms.append(f"{r['failed']} game review(s) failed")
    if r["running"] and prev and prev.get("reviews", {}).get("running"):
        alarms.append("game reviews have been running since the last check "
                      "— the analysis worker may be stuck")
    L.append(f"  reviews: {r['done']} done, {r['running']} in flight, "
             f"{r['failed']} failed")

    if g.get("longest"):
        L.append(f"  longest game so far: {g['longest']['plies']} plies — "
                 f"{SITE}/#/game/{g['longest']['id']}")

    if stats.get("ladder"):
        L.append("")
        L.append("Ladder")
        for i, pl in enumerate(stats["ladder"], 1):
            tag = " BOT" if pl["bot"] else ""
            t = f"{pl['title']} " if pl.get("title") else ""
            prov = "?" if pl["provisional"] else " "
            L.append(f"  {i}. {t}{pl['username']}{tag}  "
                     f"{pl['rating']}{prov} ({pl['games']} games)")

    L.append("")
    L.append("Nothing needs attention." if not alarms
             else "NEEDS ATTENTION:\n" + "\n".join(f"  - {a}" for a in alarms))
    return "\n".join(L), alarms


def install_task() -> int:
    """Register the Windows scheduled task. Idempotent."""
    py = shutil.which("python") or sys.executable
    script = pathlib.Path(__file__).resolve()
    # StartWhenAvailable matters: this machine is not always on at 09:00, and a
    # check that silently skips the days the computer was asleep is worse than
    # no check, because its silence looks like good news.
    xml_task = f'''<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo><Description>Daily health and activity check for murus.net</Description></RegistrationInfo>
  <Triggers><CalendarTrigger>
    <StartBoundary>2026-01-01T09:00:00</StartBoundary>
    <Enabled>true</Enabled>
    <ScheduleByDay><DaysInterval>1</DaysInterval></ScheduleByDay>
  </CalendarTrigger></Triggers>
  <Settings>
    <StartWhenAvailable>true</StartWhenAvailable>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <ExecutionTimeLimit>PT10M</ExecutionTimeLimit>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{py}</Command>
      <Arguments>"{script}"</Arguments>
      <WorkingDirectory>{script.parent.parent}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>'''
    tmp = HOME / "task.xml"
    HOME.mkdir(parents=True, exist_ok=True)
    tmp.write_text(xml_task, encoding="utf-16")
    p = subprocess.run(
        ["schtasks", "/Create", "/TN", "Murus daily check", "/XML", str(tmp), "/F"],
        capture_output=True, text=True)
    tmp.unlink(missing_ok=True)
    print(p.stdout.strip() or p.stderr.strip())
    return p.returncode


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-ssh", action="store_true",
                    help="skip the server checks, use only the public API")
    ap.add_argument("--install", action="store_true",
                    help="register the daily Windows scheduled task and exit")
    ap.add_argument("--quiet", action="store_true",
                    help="print only when something needs attention")
    args = ap.parse_args()
    if args.install:
        return install_task()

    HOME.mkdir(parents=True, exist_ok=True)
    health = []
    for name, path in (("site", "/"), ("api", "/api/stats")):
        code, secs, body = get(SITE + path)
        health.append((name, code, secs))
        if path == "/api/stats":
            stats = body

    if not stats:
        msg = (f"murus.net — {dt.datetime.now():%A %d %B %Y, %H:%M}\n\n"
               "  FAIL the site did not return statistics.\n" +
               "\n".join(f"       {n}: {c}" for n, c, _ in health) +
               "\n\nNEEDS ATTENTION:\n  - the site is unreachable or broken")
        print(msg)
        (HOME / "latest.txt").write_text(msg, encoding="utf-8")
        return 1

    prev = None
    hist = load_history()
    if hist:
        prev = hist[-1]

    server = None if args.no_ssh else server_facts()
    text, alarms = report(stats, health, server, prev)

    snapshot = {"at": dt.datetime.now().isoformat(timespec="seconds"), **stats}
    with (HOME / "history.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(snapshot) + "\n")
    (HOME / "latest.txt").write_text(text, encoding="utf-8")

    if alarms or not args.quiet:
        print(text)
    return 1 if alarms else 0


if __name__ == "__main__":
    raise SystemExit(main())
