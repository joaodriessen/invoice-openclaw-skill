"""
Invoice validation — preflight checks and post-build accuracy checks.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

from btw import resolve_btw, VALID_TYPES

ICLOUD_NUMBERS = Path.home() / "Library/Mobile Documents/com~apple~Numbers/Documents"

# ── Invoice number detection ──────────────────────────────────────────────────

def scan_invoice_numbers() -> list[int]:
    """Return all invoice numbers found across all year folders in iCloud Numbers."""
    numbers: list[int] = []
    if not ICLOUD_NUMBERS.exists():
        return numbers
    for year_dir in ICLOUD_NUMBERS.iterdir():
        if not year_dir.is_dir():
            continue
        for f in year_dir.iterdir():
            m = re.search(r"[Ff]actuur\s+(\d+)", f.name)
            if m:
                numbers.append(int(m.group(1)))
    return sorted(numbers)


def next_invoice_number() -> int:
    nums = scan_invoice_numbers()
    return (max(nums) + 1) if nums else 1


# ── Required field definitions ────────────────────────────────────────────────

REQUIRED_TOP = ["opdrachtgever", "project", "line_items"]
REQUIRED_ITEM = ["omschrijving", "bedrag", "btw_type"]

SEND_EMAIL_REQUIRED = ["email_to"]


# ── Preflight ─────────────────────────────────────────────────────────────────

def preflight(data: dict[str, Any]) -> dict[str, Any]:
    """
    Check whether enough information is present to create an invoice.
    Returns {"status": "ok", ...} or {"status": "missing_fields", "missing": [...], "questions": [...]}.
    """
    missing: list[str] = []
    questions: list[str] = []

    # Top-level required fields
    for field in REQUIRED_TOP:
        if not data.get(field):
            missing.append(field)

    if not data.get("opdrachtgever"):
        questions.append("Wie is de opdrachtgever (naam van het bedrijf of de persoon)?")

    if not data.get("project"):
        missing.append("project")
        questions.append(
            "Wat is de projectnaam? Dit verschijnt in de e-mailonderwerp "
            "(bijv. 'Optreden Noordwijk', 'Muziekles maart 2026')."
        )

    if not data.get("address"):
        missing.append("address")
        questions.append("Wat is het factuuradres (straat + postcode + stad, op aparte regels)?")

    # Line items
    items = data.get("line_items", [])
    if not items:
        questions.append(
            "Wat zijn de werkzaamheden op de factuur? "
            "Geef per regel: omschrijving, bedrag (excl. BTW), type werk "
            f"(opties: {', '.join(VALID_TYPES)}), en optioneel de datum."
        )
    else:
        for i, item in enumerate(items, 1):
            for field in REQUIRED_ITEM:
                if field not in item or item[field] in (None, "") or (field != "bedrag" and item[field] == 0):
                    missing.append(f"line_items[{i}].{field}")
                    if field == "btw_type":
                        questions.append(
                            f"Regel {i} ({item.get('omschrijving', '?')}): "
                            f"wat is het type werk? ({', '.join(VALID_TYPES)})"
                        )
                    elif field == "bedrag":
                        questions.append(f"Regel {i} ({item.get('omschrijving', '?')}): wat is het bedrag (excl. BTW)?")

    # Email
    if data.get("send_email") and not data.get("email_to"):
        missing.append("email_to")
        questions.append("Naar welk e-mailadres moet de factuur worden verstuurd?")

    if missing:
        return {
            "status": "missing_fields",
            "missing": missing,
            "questions": questions,
        }

    # Detect next invoice number (informational — agent confirms before creating)
    detected_number = data.get("invoice_number") or next_invoice_number()
    proposed_project = data.get("project") or data.get("opdrachtgever", "")

    return {
        "status": "ok",
        "detected_next_invoice_number": detected_number,
        "proposed_invoice_number": detected_number,
        "proposed_opdrachtgever": data.get("opdrachtgever", ""),
        "proposed_project": proposed_project,
        "proposed_filename": f"Factuur {detected_number}",
        "note": (
            f"Volgende factuurnummer op basis van iCloud-scan: {detected_number}. "
            "Bevestig of gebruik 'invoice_number' om te overschrijven."
        ),
    }


# ── Post-build validation ─────────────────────────────────────────────────────

def validate_invoice(data: dict[str, Any]) -> dict[str, Any]:
    """
    Validate invoice data for accuracy before creating the Numbers file.
    Returns {"errors": [...], "warnings": [...]}
    """
    errors: list[str] = []
    warnings: list[str] = []

    items = data.get("line_items", [])
    today = date.today()

    for i, item in enumerate(items, 1):
        label = item.get("omschrijving") or f"Regel {i}"

        # Bedrag
        bedrag = item.get("bedrag")
        if bedrag is None:
            errors.append(f"{label}: bedrag ontbreekt.")
        elif not isinstance(bedrag, (int, float)):
            errors.append(f"{label}: bedrag moet een getal zijn, niet '{bedrag}'.")
        elif bedrag < 0:
            errors.append(f"{label}: bedrag mag niet negatief zijn (opgegeven: {bedrag}).")
        else:
            # Two decimal places check
            if round(bedrag, 2) != bedrag:
                warnings.append(
                    f"{label}: bedrag {bedrag} heeft meer dan 2 decimalen — "
                    f"wordt afgerond naar {round(bedrag, 2)}."
                )

        # BTW type
        btw_type = item.get("btw_type", "")
        try:
            resolve_btw(btw_type)
        except ValueError as e:
            errors.append(f"{label}: {e}")

        # Datum (optional — warn if in the future)
        datum_str = item.get("datum")
        if datum_str:
            try:
                item_date = datetime.strptime(datum_str, "%Y-%m-%d").date()
                if item_date > today:
                    warnings.append(
                        f"{label}: datum {datum_str} ligt in de toekomst. "
                        "Facturen worden normaal achteraf verstuurd."
                    )
            except ValueError:
                errors.append(
                    f"{label}: datum '{datum_str}' heeft ongeldig formaat. "
                    "Gebruik YYYY-MM-DD."
                )

    # Invoice date
    inv_date_str = data.get("date")
    if inv_date_str:
        try:
            inv_date = datetime.strptime(inv_date_str, "%Y-%m-%d").date()
            if inv_date > today:
                warnings.append(
                    f"Factuurdatum {inv_date_str} ligt in de toekomst."
                )
        except ValueError:
            errors.append(
                f"Factuurdatum '{inv_date_str}' heeft ongeldig formaat. Gebruik YYYY-MM-DD."
            )

    # Address
    address = data.get("address", [])
    if isinstance(address, str):
        errors.append(
            "Adres moet een lijst zijn, niet een string. "
            "Gebruik: [\"Straatnaam 1\", \"1234 AB Stad\"]"
        )
    elif isinstance(address, list):
        if len(address) < 2:
            warnings.append(
                "Adres heeft slechts één regel. Normaal zijn dat er twee "
                "(straat + postcode/stad)."
            )
        elif len(address) > 2:
            warnings.append(
                f"Adres heeft {len(address)} regels — alleen de eerste twee worden gebruikt."
            )
        for j, line in enumerate(address, 1):
            if not line.strip():
                errors.append(f"Adresregel {j} is leeg.")

    # BTW totals cross-check
    if not errors:
        subtotaal = round(sum(item.get("bedrag", 0) for item in items), 2)
        btw_total = 0.0
        for item in items:
            try:
                rate = resolve_btw(item.get("btw_type", ""))
                btw_total += round(item["bedrag"] * rate, 2)
            except ValueError:
                pass
        btw_total = round(btw_total, 2)
        totaal = round(subtotaal + btw_total, 2)

        # Sanity check: totaal should never be less than subtotaal
        if totaal < subtotaal:
            errors.append(
                f"Totaal (€ {totaal}) is lager dan subtotaal (€ {subtotaal}) — "
                "controleer de BTW-berekening."
            )

    return {"errors": errors, "warnings": warnings}
