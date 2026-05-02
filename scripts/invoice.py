#!/usr/bin/env python3
"""
invoice-openclaw-skill — main entry point

Usage:
    python3 scripts/invoice.py '<json>'
    echo '<json>' | python3 scripts/invoice.py

Actions:
    preflight   Check required fields; return next invoice number. Run this first.
    create      Build Numbers file, export PDF, optionally draft email.
    validate    Validate invoice data without creating anything.

Run from workspace root or skill root — scripts/ is added to sys.path automatically.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow imports from scripts/ regardless of cwd
sys.path.insert(0, str(Path(__file__).parent))

from btw import resolve_btw
from mail_ops import draft_email
from numbers_ops import create_invoice, resolve_output_paths
from validation import next_invoice_number, preflight, validate_invoice


def _read_input() -> dict:
    """Read JSON from first CLI arg or stdin."""
    if len(sys.argv) > 1:
        raw = sys.argv[1]
    else:
        raw = sys.stdin.read()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        _fail(f"Ongeldige JSON invoer: {e}")


def _out(data: dict) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def _fail(message: str) -> None:
    _out({"status": "error", "message": message})
    sys.exit(1)


def _resolve_invoice_number(data: dict) -> int:
    """Use provided invoice_number or auto-detect next."""
    if "invoice_number" in data and data["invoice_number"]:
        return int(data["invoice_number"])
    return next_invoice_number()


def _normalise_items(data: dict) -> None:
    """Resolve btw_type → _rate and normalise amounts in-place."""
    for item in data.get("line_items", []):
        item["bedrag"] = round(float(item["bedrag"]), 2)
        item["_rate"] = resolve_btw(item.get("btw_type", ""))


def _default_date() -> str:
    return datetime.today().strftime("%Y-%m-%d")


LEDGER_PATH = Path.home() / ".openclaw" / "workspace" / "memory" / "invoices-ledger.json"

def _write_ledger(data: dict, result: dict) -> None:
    """Append invoice to the Mission Control finance ledger. Non-fatal."""
    entry = {
        "invoice_number": result["invoice_number"],
        "date": data.get("date", _default_date()),
        "opdrachtgever": data.get("opdrachtgever", ""),
        "project": data.get("project") or data.get("opdrachtgever", ""),
        "subtotaal": result["subtotaal"],
        "btw": result["btw"],
        "totaal": result["totaal"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        ledger = json.loads(LEDGER_PATH.read_text()) if LEDGER_PATH.exists() else []
        if not any(e.get("invoice_number") == entry["invoice_number"] for e in ledger):
            ledger.append(entry)
            LEDGER_PATH.write_text(json.dumps(ledger, ensure_ascii=False, indent=2))
    except Exception:
        pass  # ledger write failure is non-fatal


# ── Action handlers ───────────────────────────────────────────────────────────

def action_preflight(data: dict) -> None:
    result = preflight(data)
    _out(result)


def action_validate(data: dict) -> None:
    result = validate_invoice(data)
    if result["errors"]:
        _out({"status": "validation_failed", **result})
    else:
        _out({"status": "ok", **result})


def action_create(data: dict) -> None:
    # 1. Preflight
    pre = preflight(data)
    if pre["status"] == "missing_fields":
        _out(pre)
        return

    # 2. Resolve invoice number and date
    data.setdefault("date", _default_date())
    data["invoice_number"] = _resolve_invoice_number(data)

    # 3. Validate
    val = validate_invoice(data)
    if val["errors"]:
        _out({
            "status": "validation_failed",
            "errors": val["errors"],
            "warnings": val.get("warnings", []),
            "message": (
                "Factuur niet aangemaakt — los de fouten op en probeer opnieuw."
            ),
        })
        return

    # 4. Normalise
    _normalise_items(data)

    # 5. Warn about output paths before writing
    numbers_path, pdf_path = resolve_output_paths(data)
    if numbers_path.exists():
        _out({
            "status": "error",
            "message": (
                f"Bestand bestaat al: {numbers_path}\n"
                "Gebruik een ander factuurnummer of verwijder het bestand eerst."
            ),
        })
        return

    # 6. Create Numbers file and PDF
    result = create_invoice(data)
    if result["status"] != "ok":
        _out(result)
        return

    # 7. Draft email (optional)
    email_result = None
    if data.get("send_email") or data.get("email_to"):
        email_result = draft_email(data, result)

    # 8. Build final output. Keep the PDF: Apple Mail may degrade to a mailto
    # draft without attachment, and the user still needs the file.
    output: dict = {
        "status": "ok",
        "invoice_number": data["invoice_number"],
        "numbers_file": result["numbers_file"],
        "pdf_file": result["pdf_file"],
        "subtotaal": result["subtotaal"],
        "btw": result["btw"],
        "totaal": result["totaal"],
    }
    if val.get("warnings"):
        output["warnings"] = val["warnings"]
    if email_result:
        output["email"] = email_result

    _write_ledger(data, result)
    _out(output)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    data = _read_input()
    action = data.get("action", "create")

    if action == "preflight":
        action_preflight(data)
    elif action == "validate":
        action_validate(data)
    elif action == "create":
        action_create(data)
    else:
        _fail(f"Onbekende actie: '{action}'. Gebruik: preflight, validate, create.")


if __name__ == "__main__":
    main()
