# invoice-openclaw-skill

Invoice generation skill for OpenClaw — creates Dutch ZZP invoices via Apple Numbers, exports to PDF, and drafts Apple Mail messages.

## Requirements

- macOS with Numbers and Mail installed
- Python 3.9+
- No additional dependencies (uses only stdlib + osascript)

## Setup

No setup required. The skill bundles its own blank Numbers template (`templates/blank.numbers`).

The template is pre-filled with Joao's contact details, KvK, BTW-ID, and IBAN.

## Usage

```bash
python3 scripts/invoice.py '<json>'
```

See `SKILL.md` for the full agent-facing interface and all options.

## BTW rules (Dutch ZZP musician)

| Work type | Rate | Legal basis |
|-----------|------|-------------|
| Optredens / concerten / repetities | 9% | Verlaagd tarief culturele diensten |
| Muziekles aan particulieren < 21 | 0% | Vrijgesteld art. 11 lid 1 letter o Wet OB |
| Muziekles aan particulieren ≥ 21 | 21% | Standaardtarief |

## Invoice storage

`~/Library/Mobile Documents/com~apple~Numbers/Documents/<year>/Factuur <N> - <Project>.numbers`

## Invoice numbering

Auto-detected by scanning all year folders in the iCloud Numbers directory.
Can be overridden with `"invoice_number": <N>` in the JSON input.

## Updating the template

Replace `templates/blank.numbers` with a new Numbers file.
The skill expects:
- Sheet named `Invoice`
- Table named `Recipient Information` with the layout described in `SKILL.md`
- Table named `Invoice Table` with header row + 10 blank item rows + subtotaal/BTW/totaal rows
