"""
Apple Mail bridge, creates a draft invoice email.

Strategy:
  1. Try AppleScript (supports auto-attachment, full draft creation).
  2. Fall back to mailto: URL if AppleScript fails or times out (Mail busy
     syncing). In this case the compose window opens but the user must attach
     the PDF manually, and the result is reported as degraded.

Sender: joaodriessen@gmail.com (Google account configured in Mail)
Subject: Factuur <N>: <Project>
Status: draft, not auto-sent, always opened for review.
"""

from __future__ import annotations

import subprocess
import urllib.parse
from pathlib import Path
from typing import Any


SENDER = "joaodriessen@gmail.com"
APPLESCRIPT_TIMEOUT = 45  # seconds; Mail can be slow when syncing


def _esc(text: str) -> str:
    return str(text).replace('"', "'").replace("\\", "/")


def _build_applescript(
    to_address: str,
    subject: str,
    body_lines: list[str],
    pdf_path: str,
) -> str:
    to_esc = _esc(to_address)
    subject_esc = _esc(subject)
    pdf_esc = _esc(pdf_path)
    body_as = " & return & ".join(f'"{_esc(line)}"' for line in body_lines)

    lines = [
        'tell application "Mail"',
        f'    set msgBody to {body_as}',
        '    set newMsg to make new outgoing message',
        f'    set sender of newMsg to "{SENDER}"',
        f'    set subject of newMsg to "{subject_esc}"',
        '    set content of newMsg to msgBody',
        '    tell newMsg',
        f'        make new to recipient with properties {{address: "{to_esc}"}}',
        f'        make new attachment with properties {{file name: POSIX file "{pdf_esc}"}}',
        '    end tell',
        '    set visible of newMsg to true',
        '    activate',
        'end tell',
        'return "ok"',
    ]
    return "\n".join(lines)


def _try_applescript(
    to_address: str,
    subject: str,
    body_lines: list[str],
    pdf_path: str,
) -> tuple[bool, str | None]:
    """Try creating the draft via AppleScript."""
    script = _build_applescript(to_address, subject, body_lines, pdf_path)
    try:
        proc = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=APPLESCRIPT_TIMEOUT,
        )
        if proc.returncode == 0:
            return True, None
        detail = (proc.stderr or proc.stdout or "").strip()
        return False, detail or f"osascript exited with {proc.returncode}"
    except subprocess.TimeoutExpired:
        return False, f"AppleScript timed out after {APPLESCRIPT_TIMEOUT}s"


def _open_mailto(to_address: str, subject: str, body_lines: list[str]) -> bool:
    """Open a mailto: URL — always works, but cannot auto-attach PDF."""
    body = "\n".join(body_lines)
    url = (
        "mailto:"
        + urllib.parse.quote(to_address, safe="@")
        + "?subject=" + urllib.parse.quote(subject)
        + "&body=" + urllib.parse.quote(body)
    )
    proc = subprocess.run(["open", url], check=False)
    return proc.returncode == 0


def _email_greeting(opdrachtgever: str) -> str:
    opdrachtgever = opdrachtgever.strip()
    return f"Beste {opdrachtgever}," if opdrachtgever else "Beste,"


def _email_description(invoice: dict[str, Any]) -> str:
    items = invoice.get("line_items", [])
    first_item = items[0] if items else {}
    datum = first_item.get("datum")
    if datum:
        try:
            human_date = f"{int(datum[8:10])} {['januari','februari','maart','april','mei','juni','juli','augustus','september','oktober','november','december'][int(datum[5:7]) - 1]} {datum[0:4]}"
        except Exception:
            human_date = datum
        return f"Bijgevoegd de factuur voor {first_item.get('omschrijving', 'de werkzaamheden')} op {human_date}."
    return f"Bijgevoegd de factuur voor {first_item.get('omschrijving', 'de werkzaamheden')}."


def draft_email(invoice: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    """
    Open a Mail draft with PDF attached.
    Tries AppleScript first; falls back to mailto: if Mail is unresponsive.

    Returns a status dict for the agent to report to the user.
    """
    to_address = invoice.get("email_to", "")
    if not to_address:
        return {"status": "skipped", "reason": "Geen e-mailadres opgegeven."}

    pdf_path = result.get("pdf_file", "")
    if not pdf_path or not Path(pdf_path).exists():
        return {
            "status": "error",
            "reason": "PDF niet gevonden, e-mail concept niet aangemaakt.",
        }

    inv_num = invoice["invoice_number"]
    project = invoice.get("project") or invoice.get("opdrachtgever", "Factuur")
    opdrachtgever = invoice.get("opdrachtgever", "")

    subject = f"Factuur {inv_num}: {project}"

    body_lines = [
        _email_greeting(opdrachtgever),
        "",
        _email_description(invoice),
        "",
        "Met vriendelijke groet,",
        "Joao Driessen",
    ]

    # Try AppleScript (auto-attaches PDF)
    success, applescript_error = _try_applescript(
        to_address, subject, body_lines, pdf_path
    )
    if success:
        return {
            "status": "ok",
            "method": "applescript",
            "subject": subject,
            "to": to_address,
            "sender": SENDER,
            "pdf_attached": True,
            "pdf_file": pdf_path,
            "note": "Concept geopend in Mail met bijlage — controleer en verstuur handmatig.",
        }

    # Fallback: mailto URL (no attachment)
    mailto_opened = _open_mailto(to_address, subject, body_lines)
    if not mailto_opened:
        return {
            "status": "error",
            "method": "mailto",
            "subject": subject,
            "to": to_address,
            "sender": SENDER,
            "pdf_attached": False,
            "pdf_file": pdf_path,
            "reason": (
                "AppleScript kon de PDF niet bijvoegen en mailto kon geen "
                "concept openen."
            ),
            "applescript_error": applescript_error,
        }

    return {
        "status": "degraded",
        "method": "mailto",
        "subject": subject,
        "to": to_address,
        "sender": SENDER,
        "pdf_attached": False,
        "pdf_file": pdf_path,
        "reason": "AppleScript kon de PDF niet automatisch bijvoegen.",
        "applescript_error": applescript_error,
        "note": (
            f"Mail-concept geopend via mailto (PDF niet automatisch bijgevoegd). "
            f"Voeg de PDF handmatig toe: {pdf_path}"
        ),
    }
