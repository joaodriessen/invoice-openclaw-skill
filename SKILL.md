---
name: invoice
description: Maak facturen aan voor Joao's ZZP-werkzaamheden. Vult een Numbers-template, exporteert naar PDF en maakt een e-mailconcept aan in Apple Mail. Gebruik dit altijd wanneer de gebruiker een factuur wil maken, factuurnummer wil weten, of een factuur wil versturen.
tools: python3, osascript
tags: finance, invoice, factuur, numbers, pdf, mail, btw, zzp
---

# Invoice Skill

Maakt facturen op basis van een Numbers-template, exporteert naar PDF, en maakt een e-mailconcept aan in Apple Mail.

## Workflow

**Altijd in deze volgorde:**
1. Roep `preflight` aan — controleer of alle benodigde informatie aanwezig is.
2. Als er velden ontbreken: stel de gebruiker de vragen uit `questions[]`.
3. **Bevestig met de gebruiker** — toon een samenvatting van wat er aangemaakt gaat worden:
   - Factuurnummer (`proposed_invoice_number`)
   - Opdrachtgever (`proposed_opdrachtgever`)
   - Project (`proposed_project`) — dit verschijnt in de e-mailonderwerp en bestandsnaam
   - Regelposten: omschrijving + bedrag per item
   - Wacht op expliciete bevestiging ("ja", "klopt", "go ahead") voor je `create` aanroept.

**Projectnaam — nooit raden of afleiden.** Als de gebruiker geen expliciete projectnaam heeft opgegeven, stel de vraag: "Wat is de projectnaam? (bijv. 'Optreden Noordwijk')" — ook al staat de naam mogelijk in de context. De gebruiker beslist zelf wat erop de factuur komt.
4. Roep `create` aan met volledige data.
5. Meld de gebruiker het resultaat: factuurnummer, locatie, totaalbedrag.

## Commando

```bash
/opt/homebrew/bin/python3 skills/invoice/scripts/invoice.py '<json>'
```

Of via stdin:
```bash
echo '<json>' | /opt/homebrew/bin/python3 skills/invoice/scripts/invoice.py
```

## Actions

### `preflight` — controleer vereiste velden

Altijd eerst uitvoeren. Geeft het volgende factuurnummer terug en toont ontbrekende velden.

**Input:**
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

**Output (alles aanwezig):**
```json
{
  "status": "ok",
  "detected_next_invoice_number": 528,
  "proposed_invoice_number": 528,
  "proposed_opdrachtgever": "Groove Music Productions",
  "proposed_project": "Groove Music Productions",
  "proposed_filename": "Factuur 528",
  "note": "Volgende factuurnummer op basis van iCloud-scan: 528. ..."
}
```

**Output (ontbrekende velden):**
```json
{
  "status": "missing_fields",
  "missing": ["address"],
  "questions": ["Wat is het factuuradres (straat + postcode + stad, op aparte regels)?"]
}
```

---

### `create` — maak factuur aan

**Minimale input:**
```json
{
  "action": "create",
  "opdrachtgever": "Groove Music Productions",
  "address": ["Fazantenhof 115", "3755 EG Eemnes"],
  "line_items": [
    {
      "omschrijving": "Optreden Royal Dutch Scam",
      "bedrag": 1140.50,
      "btw_type": "optreden",
      "datum": "2026-03-15"
    }
  ]
}
```

**Alle velden:**
```json
{
  "action": "create",
  "project": "Royal Dutch Scam",
  "opdrachtgever": "Groove Music Productions",
  "address": ["Fazantenhof 115", "3755 EG Eemnes"],
  "date": "2026-04-03",
  "invoice_number": 528,
  "line_items": [
    {
      "omschrijving": "Optreden",
      "datum": "2026-02-21",
      "bedrag": 380.17,
      "btw_type": "optreden"
    },
    {
      "omschrijving": "Muziekles (groep onder 21)",
      "datum": "2026-03-10",
      "bedrag": 200.00,
      "btw_type": "les"
    }
  ],
  "send_email": true,
  "email_to": "masja@groovemusicproductions.com"
}
```

**Output (succes):**
```json
{
  "status": "ok",
  "invoice_number": 528,
  "numbers_file": "~/Library/Mobile Documents/com~apple~Numbers/Documents/2026/Factuur 528 - Royal Dutch Scam.numbers",
  "pdf_file": "~/Library/Mobile Documents/com~apple~Numbers/Documents/2026/Factuur 528 - Royal Dutch Scam.pdf",
  "subtotaal": 1580.17,
  "btw": { "BTW 9%": 34.22, "BTW vrijgesteld": 0.0 },
  "totaal": 1614.39,
  "email": {
    "status": "ok",
    "subject": "Factuur 528: Royal Dutch Scam",
    "to": "masja@groovemusicproductions.com",
    "note": "Concept geopend in Mail — controleer en verstuur handmatig."
  }
}
```

---

### `validate` — controleer data zonder aan te maken

```json
{
  "action": "validate",
  "line_items": [...]
}
```

---

## BTW-types

| Type | Rate | Wanneer |
|------|------|---------|
| `optreden` | 9% | Optredens, concerten, uitvoeringen |
| `concert` | 9% | Alias voor optreden |
| `repetitie` | 9% | Repetities, bandrepetities |
| `les` | 0% | Muziekles aan particulieren onder 21 jaar (vrijgesteld) |
| `muziekles` | 0% | Alias voor les |
| `onderwijs` | 0% | Alias voor les |
| `les_21plus` | 21% | Muziekles aan particulieren van 21 jaar en ouder |
| `cursus_21plus` | 21% | Cursussen aan 21+ |

Je kunt ook een percentage opgeven: `"btw_type": "9"`, `"btw_type": "0"`, `"btw_type": "21"`.

## Vereiste velden

| Veld | Vereist | Standaard |
|------|---------|-----------|
| `opdrachtgever` | ja | — |
| `address` | ja | — |
| `line_items[].omschrijving` | ja | — |
| `line_items[].bedrag` | ja | — |
| `line_items[].btw_type` | ja | — |
| `project` | ja | — (bijv. "Optreden Noordwijk") |
| `date` | nee | vandaag |
| `invoice_number` | nee | auto (scan iCloud) |
| `line_items[].datum` | nee | leeg |
| `send_email` | nee | false |
| `email_to` | nee (verplicht als send_email=true) | — |

## Opslag

Facturen worden opgeslagen in:
`~/Library/Mobile Documents/com~apple~Numbers/Documents/<jaar>/Factuur <N> - <Project>.numbers`

PDF in dezelfde map.

## Validatie

De skill controleert automatisch:
- Alle verplichte velden aanwezig
- Bedragen > 0 en max 2 decimalen
- BTW correct berekend per type
- Datums geldig (YYYY-MM-DD) en niet in de toekomst
- Adres heeft twee regels
- Totaal = subtotaal + BTW

## Meerdere BTW-tarieven

Eén factuur mag meerdere BTW-tarieven bevatten (bijv. een optreden + muziekles).
De skill toont dan meerdere BTW-regels in de factuur.

## E-mail

E-mail wordt aangemaakt als concept in Apple Mail (joaodriessen@gmail.com).
**Niet automatisch verstuurd** — altijd eerst controleren.
Onderwerp: `Factuur <N>: <Project>`

Standaard concepttekst:

```text
Beste <Opdrachtgever>,

Bijgevoegd de factuur voor <Omschrijving eerste regel> op <Datum eerste regel>.

Met vriendelijke groet,
Joao Driessen
```

Als er geen datum op de eerste regel staat, laat de skill het datumdeel weg.
