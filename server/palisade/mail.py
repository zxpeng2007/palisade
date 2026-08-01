"""Outgoing mail. One message in the whole site: "confirm this address".

Transport is Resend's HTTPS API — no SMTP, no spool, no retries. A send either
happens while the request is open or the caller hears about it and tells the
person to try again; a queue we would have to drain is not worth owning for one
message type.

Environment:
    PALISADE_MAIL_FROM   the From: header, e.g. ``Palisade <hello@murus.net>``
    PALISADE_RESEND_KEY  Resend API key. Absent → console mode, below.
    PALISADE_BASE_URL    where links point (default https://murus.net)

Console mode is how development and the test suite run: with no key the message
is printed to stdout, link and all, and recorded in :data:`outbox`. It is loud
on purpose. A verification link nobody can see is the same outage as a send
that failed, so the one thing this module must never do is decide that a
message it did not deliver is fine.
"""

from __future__ import annotations

import html
import os

DEFAULT_BASE_URL = "https://murus.net"
RESEND_ENDPOINT = "https://api.resend.com/emails"
TIMEOUT = 10.0
# Enough to see what a dev session or a test just sent, small enough that a
# long-lived console-mode server does not accumulate addresses forever.
OUTBOX_LIMIT = 50


class MailError(RuntimeError):
    """A message that did not go out. Callers turn this into a 502."""


#: Every message this process has sent or printed, newest last. Console mode
#: has no other record, and tests read the link out of here.
outbox: list[dict] = []


def base_url() -> str:
    return (os.environ.get("PALISADE_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")


def console_mode() -> bool:
    return not os.environ.get("PALISADE_RESEND_KEY", "").strip()


def verification_link(token: str) -> str:
    # The web client is a hash-routed SPA, so the token rides in the fragment.
    # Tokens are URL-safe base64, so nothing here needs escaping.
    return f"{base_url()}/#/verify/{token}"


def _bodies(username: str, token: str, changed: bool) -> tuple[str, str]:
    link = verification_link(token)
    opening = (
        "You asked to move your Palisade account to this address."
        if changed else
        "Someone — hopefully you — signed up to Palisade with this address."
    )
    text = f"""Hi {username},

{opening} Palisade is the wall-game arena at {base_url()}, where people and
engines play on one ladder.

Confirm the address by following this link:

    {link}

It works once, and for 24 hours. Until then you can still sign in, watch
games, and play casual ones — rated games and engine accounts are the only
things waiting behind it.

If none of this means anything to you, just ignore this mail. Nothing is
attached to your address until the link is used.

— Palisade
"""
    safe_link = html.escape(link, quote=True)
    body = f"""<p>Hi {html.escape(username)},</p>
<p>{html.escape(opening)} Palisade is the wall-game arena at
{html.escape(base_url())}, where people and engines play on one ladder.</p>
<p><a href="{safe_link}">Confirm this address</a> — the link works once, and
for 24 hours.</p>
<p>Until then you can still sign in, watch games, and play casual ones; rated
games and engine accounts are the only things waiting behind it.</p>
<p>If none of this means anything to you, just ignore this mail. Nothing is
attached to your address until the link is used.</p>
<p>— Palisade</p>
<p style="color:#888;font-size:12px">If the link does not open, paste this into
your browser:<br>{safe_link}</p>
"""
    return text, body


async def send_verification(to: str, username: str, token: str,
                            changed: bool = False) -> None:
    """Send one verification link, or raise :class:`MailError` trying."""
    text, body = _bodies(username, token, changed)
    subject = ("Confirm your new Palisade address" if changed
               else "Confirm your address for Palisade")
    await _send(to, subject, text, body)


async def _send(to: str, subject: str, text: str, body: str) -> None:
    key = os.environ.get("PALISADE_RESEND_KEY", "").strip()
    outbox.append({"to": to, "subject": subject, "text": text, "html": body,
                   "console": not key})
    del outbox[:-OUTBOX_LIMIT]

    if not key:
        print(f"[palisade mail] console mode: no PALISADE_RESEND_KEY, so this "
              f"message was not sent. To: {to}\nSubject: {subject}\n{text}",
              flush=True)
        return

    sender = os.environ.get("PALISADE_MAIL_FROM", "").strip()
    if not sender:
        # Resend rejects an unverified sender anyway; failing here says why.
        raise MailError("PALISADE_RESEND_KEY is set but PALISADE_MAIL_FROM is not")

    # Imported here so a deployment that never leaves console mode does not
    # need an HTTP client installed at all.
    import httpx

    payload = {"from": sender, "to": [to], "subject": subject,
               "text": text, "html": body}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(
                RESEND_ENDPOINT, json=payload,
                headers={"Authorization": f"Bearer {key}"})
    except httpx.HTTPError as e:
        # Only the exception's class name: the key lives in a header, and a
        # verbose transport error is the sort of thing that ends up in a log
        # with the request echoed back.
        raise MailError(f"mail transport failed ({type(e).__name__})") from None

    if response.status_code // 100 != 2:
        # Resend's error bodies name the problem (unverified domain, bad
        # recipient) and never quote the key back. Trim: they can be long.
        raise MailError(f"mail provider refused the message "
                        f"(HTTP {response.status_code}): {response.text[:200]}")
