"""
Numbers bridge — creates an invoice by filling a Numbers template via AppleScript.

Template structure (blank.numbers):
  Sheet "Invoice":
    Table "Recipient Information" (17r × 3c):
      R12C2 = Project, R13C2 = Opdrachtgever, R14C2 = Adres regel 1,
      R15C2 = Adres regel 2, R16C2 = Factuur Nummer, R17C2 = Datum
    Table "Invoice Table" (14r × 4c):
      R1    = header (Omschrijving | Datum | Uur/KM | Bedrag)
      R2–R11 = 10 blank line-item rows
      R12   = Subtotaal row  (C3="Subtotaal", C4=amount)
      R13   = BTW row        (C2="BTW", C3=rate, C4=amount)
      R14   = Totaal row     (C3="Totaal", C4=amount)

Dynamic behaviour:
  N ≤ 10 items → delete unused rows from bottom (R11 down to R(N+2))
  N > 10 items → insert rows before subtotaal for each extra item
  Multiple BTW rates → insert extra BTW rows after first
"""

from __future__ import annotations

import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from btw import dutch_round, resolve_btw, label as btw_label

ICLOUD_NUMBERS = Path.home() / "Library/Mobile Documents/com~apple~Numbers/Documents"
TEMPLATE = Path(__file__).parent.parent / "templates" / "blank.numbers"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _esc(text: str) -> str:
    """Escape a string for embedding in an AppleScript quoted string."""
    # AppleScript has no backslash escape — replace " with ' (safe for names/addresses)
    return str(text).replace('"', "'").replace("\\", "/")


def _as_date(date_str: str) -> str:
    """Convert YYYY-MM-DD to AppleScript date literal."""
    d = datetime.strptime(date_str, "%Y-%m-%d")
    months = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ]
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    return f'{days[d.weekday()]}, {d.day} {months[d.month - 1]} {d.year} at 00:00:00'


def _fmt_num(n: float) -> str:
    """Format a float for AppleScript (always use . as decimal separator)."""
    return f"{round(n, 2):.2f}"


# ── AppleScript generator ─────────────────────────────────────────────────────

def _build_script(
    numbers_path: str,
    pdf_path: str,
    invoice: dict[str, Any],
) -> str:
    items = invoice["line_items"]
    N = len(items)

    # Resolve BTW rates per item
    for item in items:
        item["_rate"] = resolve_btw(item["btw_type"])

    # Group totals by BTW rate
    btw_groups: dict[float, float] = {}
    for item in items:
        rate = item["_rate"]
        btw_groups[rate] = dutch_round(btw_groups.get(rate, 0.0) + item["bedrag"])

    btw_sorted = sorted(btw_groups.items())  # ascending rate order
    subtotaal = dutch_round(sum(item["bedrag"] for item in items))
    btw_total = dutch_round(sum(dutch_round(base * rate) for rate, base in btw_sorted))
    totaal = dutch_round(subtotaal + btw_total)

    lines: list[str] = []
    a = lines.append  # shorthand

    a('tell application "Numbers"')
    a(f'    set doc to open POSIX file "{numbers_path}"')
    a('    set s to sheet 1 of doc')
    a('    set t1 to table "Recipient Information" of s')
    a('    set t2 to table "Invoice Table" of s')
    a('')

    # ── Recipient Information ──
    project = _esc(invoice.get("project") or invoice.get("opdrachtgever", ""))
    opdrgvr = _esc(invoice["opdrachtgever"])
    addr = invoice.get("address", [])
    addr1 = _esc(addr[0]) if len(addr) > 0 else ""
    addr2 = _esc(addr[1]) if len(addr) > 1 else ""
    inv_num = invoice["invoice_number"]
    inv_date = _as_date(invoice.get("date", datetime.today().strftime("%Y-%m-%d")))

    a(f'    set value of cell 12 of column 2 of t1 to "{project}"')
    a(f'    set value of cell 13 of column 2 of t1 to "{opdrgvr}"')
    a(f'    set value of cell 14 of column 2 of t1 to "{addr1}"')
    a(f'    set value of cell 15 of column 2 of t1 to "{addr2}"')
    a(f'    set value of cell 16 of column 2 of t1 to {inv_num}')
    a(f'    set value of cell 17 of column 2 of t1 to (date "{inv_date}")')
    a('')

    # ── Clear Uur/KM header ──
    a('    set value of cell 1 of column 3 of t2 to ""')
    a('')

    # ── Line items ──
    # Template has rows 2–11 (10 slots). Rows 2..min(N,10)+1 get filled.
    # If N > 10: insert rows before the current subtotaal row for extras.
    # If N < 10: delete unused rows from bottom.

    for i, item in enumerate(items):
        row = i + 2  # rows are 1-indexed; header is R1; items start at R2

        if row <= 11:
            # Row already exists in template
            pass
        else:
            # Insert a row above the current subtotaal position.
            # After (i-10) prior insertions, subtotaal is at row 12 + (i - 10) = i + 2.
            subtotaal_row_now = i + 2
            a(f'    add row above (row {subtotaal_row_now} of t2)')

        omsch = _esc(item["omschrijving"])
        bedrag = _fmt_num(item["bedrag"])

        a(f'    set value of cell {row} of column 1 of t2 to "{omsch}"')

        datum_str = item.get("datum")
        if datum_str:
            a(f'    set value of cell {row} of column 2 of t2 to (date "{_as_date(datum_str)}")')
        else:
            a(f'    set value of cell {row} of column 2 of t2 to ""')

        a(f'    set value of cell {row} of column 3 of t2 to ""')  # Uur/KM always empty
        a(f'    set value of cell {row} of column 4 of t2 to {bedrag}')

    a('')

    # ── Delete unused rows (N < 10) ──
    # Delete from row 11 down to row N+2 (the first unused item row).
    if N < 10:
        for row in range(11, N + 1, -1):
            a(f'    delete row {row} of t2')
        a('')

    # After adjustments, totals are at:
    #   subtotaal = N+2, first BTW = N+3, totaal = N+3+len(btw_sorted)
    subtotaal_row = N + 2
    first_btw_row = subtotaal_row + 1

    # ── Subtotaal ──
    a(f'    set value of cell {subtotaal_row} of column 3 of t2 to "Subtotaal"')
    a(f'    set value of cell {subtotaal_row} of column 4 of t2 to {_fmt_num(subtotaal)}')
    a('')

    # ── BTW rows ──
    # Template has exactly one BTW row. If multiple rates, insert extras.
    for j, (rate, base) in enumerate(btw_sorted):
        btw_row = first_btw_row + j
        btw_amount = dutch_round(base * rate)
        rate_label = btw_label(rate)

        if j > 0:
            # Insert a row above the current totaal row (which shifts down by 1 each time)
            totaal_row_now = first_btw_row + j  # before this insertion
            a(f'    add row above (row {totaal_row_now} of t2)')

        a(f'    set value of cell {btw_row} of column 2 of t2 to "{rate_label}"')
        a(f'    set value of cell {btw_row} of column 3 of t2 to {_fmt_num(rate)}')
        a(f'    set value of cell {btw_row} of column 4 of t2 to {_fmt_num(btw_amount)}')

    a('')

    # ── Totaal ──
    totaal_row = first_btw_row + len(btw_sorted)
    a(f'    set value of cell {totaal_row} of column 3 of t2 to "Totaal"')
    a(f'    set value of cell {totaal_row} of column 4 of t2 to {_fmt_num(totaal)}')
    a('')

    # ── Restore Euro currency format on all amount cells ──
    # Setting a value via AppleScript resets cell format from currency to automatic.
    # We restore it here after all values have been written.
    a('    -- Restore Euro currency format (set value resets it to automatic)')
    for row in range(2, totaal_row + 1):
        a(f'    set format of cell {row} of column 4 of t2 to currency')
    a('')

    # ── Save and export ──
    a('    save doc')
    a(f'    export doc to POSIX file "{pdf_path}" as PDF')
    a('    close doc saving no')
    a('end tell')
    a('return "ok"')

    return "\n".join(lines)


# ── Public API ────────────────────────────────────────────────────────────────

def resolve_output_paths(invoice: dict[str, Any]) -> tuple[Path, Path]:
    """Return (numbers_path, pdf_path) for this invoice."""
    inv_num = invoice["invoice_number"]
    project = invoice.get("project") or invoice.get("opdrachtgever", "")
    year = datetime.strptime(
        invoice.get("date", datetime.today().strftime("%Y-%m-%d")), "%Y-%m-%d"
    ).year

    filename = f"Factuur {inv_num}"

    year_dir = ICLOUD_NUMBERS / str(year)
    year_dir.mkdir(parents=True, exist_ok=True)

    numbers_path = year_dir / f"{filename}.numbers"
    pdf_path = year_dir / f"{filename}.pdf"
    return numbers_path, pdf_path


def create_invoice(invoice: dict[str, Any]) -> dict[str, Any]:
    """
    Copy template, fill cells via AppleScript, export PDF.
    Returns {"status": "ok"|"error", "numbers_file": ..., "pdf_file": ..., ...}
    """
    numbers_path, pdf_path = resolve_output_paths(invoice)

    # Copy template to destination
    if not TEMPLATE.exists():
        return {
            "status": "error",
            "message": f"Template niet gevonden: {TEMPLATE}. Controleer of templates/blank.numbers aanwezig is.",
        }
    shutil.copy2(TEMPLATE, numbers_path)

    # Build and run AppleScript
    script = _build_script(str(numbers_path), str(pdf_path), invoice)

    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            # Clean up partial file
            numbers_path.unlink(missing_ok=True)
            return {
                "status": "error",
                "message": f"AppleScript fout: {result.stderr.strip()}",
            }
    except subprocess.TimeoutExpired:
        numbers_path.unlink(missing_ok=True)
        return {"status": "error", "message": "Timeout — Numbers reageerde niet binnen 60s."}

    # Calculate totals for return value — group by rate (same method as invoice)
    items = invoice["line_items"]
    subtotaal = dutch_round(sum(item["bedrag"] for item in items))
    btw_groups: dict[float, float] = {}
    for item in items:
        rate = resolve_btw(item["btw_type"])
        btw_groups[rate] = dutch_round(btw_groups.get(rate, 0.0) + item["bedrag"])
    btw_breakdown: dict[str, float] = {}
    for rate, base in sorted(btw_groups.items()):
        btw_breakdown[btw_label(rate)] = dutch_round(base * rate)
    totaal = dutch_round(subtotaal + sum(btw_breakdown.values()))

    return {
        "status": "ok",
        "invoice_number": invoice["invoice_number"],
        "numbers_file": str(numbers_path),
        "pdf_file": str(pdf_path),
        "subtotaal": subtotaal,
        "btw": btw_breakdown,
        "totaal": totaal,
    }
