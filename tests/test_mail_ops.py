from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import mail_ops


def _invoice() -> dict:
    return {
        "invoice_number": 531,
        "project": "MJO MIMIK Fleurine",
        "opdrachtgever": "MEProductions B.V.",
        "email_to": "joan@example.com",
        "line_items": [
            {
                "omschrijving": "Concert met Fleurine",
                "datum": "2026-05-02",
                "bedrag": 100,
                "btw_type": "9",
            }
        ],
    }


def test_draft_email_reports_degraded_when_mailto_fallback_lacks_attachment(tmp_path):
    pdf = tmp_path / "Factuur 531 - MJO MIMIK Fleurine.pdf"
    pdf.write_text("pdf placeholder")

    with (
        patch.object(mail_ops, "_try_applescript", return_value=(False, "Mail busy")),
        patch.object(mail_ops, "_open_mailto", return_value=True),
    ):
        result = mail_ops.draft_email(_invoice(), {"pdf_file": str(pdf)})

    assert result["status"] == "degraded"
    assert result["method"] == "mailto"
    assert result["pdf_attached"] is False
    assert result["pdf_file"] == str(pdf)
    assert "AppleScript" in result["reason"]


def test_draft_email_reports_error_when_no_draft_can_open(tmp_path):
    pdf = tmp_path / "Factuur 531 - MJO MIMIK Fleurine.pdf"
    pdf.write_text("pdf placeholder")

    with (
        patch.object(mail_ops, "_try_applescript", return_value=(False, "Mail busy")),
        patch.object(mail_ops, "_open_mailto", return_value=False),
    ):
        result = mail_ops.draft_email(_invoice(), {"pdf_file": str(pdf)})

    assert result["status"] == "error"
    assert result["pdf_attached"] is False
    assert result["pdf_file"] == str(pdf)
