# invoice-openclaw-skill

Generates Dutch ZZP invoices via Apple Numbers, exports to PDF, and drafts Apple Mail messages. All automation runs locally via AppleScript — no cloud services involved.

## What it does

1. Agent calls `preflight` with client details and line items — skill returns the next invoice number and flags any missing fields.
2. Agent confirms the summary with Joao before proceeding.
3. Agent calls `create` — skill copies the bundled `blank.numbers` template into iCloud Drive, fills in all fields via AppleScript, exports a PDF alongside the Numbers file, and (optionally) opens a draft in Apple Mail with the PDF attached.
4. Agent reports the invoice number, file location, and totals.

The Numbers file and PDF land in:

```
~/Library/Mobile Documents/com~apple~Numbers/Documents/<year>/Factuur <N> - <Project>.numbers
~/Library/Mobile Documents/com~apple~Numbers/Documents/<year>/Factuur <N> - <Project>.pdf
```

The email draft is opened in Mail but never sent automatically — always review before sending.

## Requirements

- macOS with Numbers and Mail installed
- Python 3.9+
- No additional dependencies (stdlib only + `osascript`)
- OpenClaw running — the skill is invoked via the `accountant` agent

## Setup

No setup required. The skill bundles its own blank Numbers template at `templates/blank.numbers`, pre-filled with Joao's contact details, KvK, BTW-ID, and IBAN.

## Usage

### Via the accountant agent

The accountant agent calls the skill automatically. Trigger it in OpenClaw by asking to create an invoice.

### Manual invocation

```bash
# From CLI argument
/opt/homebrew/bin/python3 ~/.openclaw/workspace/skills/invoice/scripts/invoice.py '<json>'

# From stdin
echo '<json>' | /opt/homebrew/bin/python3 ~/.openclaw/workspace/skills/invoice/scripts/invoice.py
```

Run from the workspace root or the skill root — the script adds `scripts/` to `sys.path` automatically.

### Actions

**`preflight`** — check fields and get next invoice number. Always run first.

```json
{
  "action": "preflight",
  "opdrachtgever": "Groove Music Productions",
  "address": ["Fazantenhof 115", "3755 EG Eemnes"],
  "line_items": [
    { "omschrijving": "Optreden", "bedrag": 1140.50, "btw_type": "optreden" }
  ]
}
```

**`create`** — build the Numbers file, export PDF, optionally draft email.

```json
{
  "action": "create",
  "project": "Royal Dutch Scam",
  "opdrachtgever": "Groove Music Productions",
  "address": ["Fazantenhof 115", "3755 EG Eemnes"],
  "date": "2026-04-03",
  "invoice_number": 528,
  "line_items": [
    { "omschrijving": "Optreden", "datum": "2026-02-21", "bedrag": 380.17, "btw_type": "optreden" },
    { "omschrijving": "Muziekles (groep onder 21)", "datum": "2026-03-10", "bedrag": 200.00, "btw_type": "les" }
  ],
  "send_email": true,
  "email_to": "masja@groovemusicproductions.com"
}
```

`invoice_number` and `date` are optional — both default to auto-detected values. `send_email` defaults to `false`.

**`validate`** — validate data without creating anything.

See `SKILL.md` for the full input/output reference and field list.

## BTW rules (Dutch ZZP musician)

| Work type | Rate | Legal basis |
|-----------|------|-------------|
| Optredens / concerten / repetities (`optreden`, `concert`, `repetitie`) | 9% | Verlaagd tarief culturele diensten |
| Muziekles aan particulieren < 21 (`les`, `muziekles`, `onderwijs`) | 0% | Vrijgesteld art. 11 lid 1 letter o Wet OB |
| Muziekles aan particulieren ≥ 21 (`les_21plus`, `cursus_21plus`) | 21% | Standaardtarief |

You can also pass a numeric string directly: `"btw_type": "9"`, `"btw_type": "0"`, `"btw_type": "21"`.

One invoice can carry multiple BTW rates — the skill produces separate BTW lines per rate.

## Invoice storage

```
~/Library/Mobile Documents/com~apple~Numbers/Documents/<year>/Factuur <N> - <Project>.numbers
~/Library/Mobile Documents/com~apple~Numbers/Documents/<year>/Factuur <N> - <Project>.pdf
```

The PDF is exported to the same folder as the Numbers file immediately after creation.

## Invoice numbering

Auto-detected by scanning all year folders in the iCloud Numbers directory, including Numbers documents already synced there. The scan prevents re-using existing numbers even if invoices were created outside this skill.

Override with `"invoice_number": <N>` in the JSON input.

## Repo structure

| Path | Purpose |
|------|---------|
| `scripts/invoice.py` | Entry point — parses JSON, dispatches to action handlers |
| `scripts/btw.py` | BTW type resolution and rate lookup |
| `scripts/validation.py` | Field validation, preflight logic, invoice number scan |
| `scripts/numbers_ops.py` | AppleScript automation for Numbers (fill template, export PDF) |
| `scripts/mail_ops.py` | AppleScript automation for Mail (draft with PDF attachment) |
| `templates/blank.numbers` | Bundled Numbers template |
| `SKILL.md` | Agent-facing interface — actions, fields, examples, validation rules |

## Updating the template

Replace `templates/blank.numbers` with a new Numbers file. The skill expects:

- Sheet named `Invoice`
- Table named `Recipient Information` with the layout described in `SKILL.md`
- Table named `Invoice Table` with a header row, 10 blank item rows, and subtotaal/BTW/totaal rows

## Related

- Agent context: `~/Projects/openclaw-evolution/repos/` (accountant agent config)
- OpenClaw workspace: `~/.openclaw/workspace/`
- Finance ledger: `~/.openclaw/workspace/memory/invoices-ledger.json`
