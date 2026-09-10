# v1.4.0 — nieuw tabblad "Openstaand"

Repo: https://github.com/ON3VZ/n1mm-fieldday-tracker
Datum: 10 september 2026

---

## 1. Wat er gewijzigd is

Eén toevoeging, verder niets aangepast aan bestaande functionaliteit:

**Nieuw tabblad "Openstaand" (EN: "Remaining")**, geplaatst tussen **Tabel**
en **Nog te werken**. Het toont exact dezelfde matrix als het tabblad Tabel
— zelfde kolommen, kleuren, klikbare cellen, sticky header — maar filtert
er automatisch stations uit zodra die op **alle zichtbare banden** gewerkt
zijn (groen, of `excluded`). Een station met nog minstens één open band
blijft staan. Naarmate er QSO's binnenkomen wordt de lijst dus vanzelf
korter; alle bestaande filters (band, status, categorie, sectie, zoeken)
werken gewoon mee, ook op dit tabblad.

De vernieuwing loopt mee op het bestaande ritme: de app pollt
`snapshot.json` elke 5 seconden (lokaal) en herbouwt dan het actieve
tabblad. Er is geen aparte timer of achtergrondberekening bijgekomen — het
tabblad wordt alleen berekend wanneer het effectief open staat, en de
extra filtercontrole is een simpele lus over de al zichtbare stations en
banden. Geen invloed op de UDP-listener, de sync engine of de
performantie.

### Gewijzigde bestanden (3)

```
app/version.py                  1.3.3 → 1.4.0
app/view/static/index.html      nieuw tabblad "Openstaand" tussen Tabel en Nog te werken
app/view/static/app.js          renderRemaining(), gedeelde buildMatrixTable(),
                                 i18n-strings nl/en/fr (view.remaining, remaining.none)
RELEASE-NOTES-v1.4.0.md         nieuw
```

Geen wijzigingen aan het snapshot-schema, `server.py`, de sync engine, de
publicatie naar GitHub Pages, export, of enige andere view.

### Self-check (§11.2)

- De matrixopbouw (`renderMatrix`) is ongewijzigd van gedrag: dezelfde code
  is enkel verplaatst naar een gedeelde `buildMatrixTable()`, die zowel
  Tabel als Openstaand aanroepen — geen dubbele logica.
- `stationFullyWorked()` telt een station als "af" wanneer elke zichtbare
  band `worked_by_n1mm`, `manual_worked` of `excluded` is; anders blijft
  het station staan. Manual overrides winnen zoals overal (BR-05) —
  omdat de filter op de reeds berekende celstatus werkt, niet op ruwe
  QSO-data, is er niets aan die regel geraakt.
- BR-10 (matrix start leeg bij nieuwe velddag) is niet geraakt — Openstaand
  toont dan gewoon alle stations, zoals Tabel dat ook doet.
- JS syntactisch gecontroleerd (`node --check`).
- Tab-volgorde, i18n-koppeling (`data-i18n`) en de views-lookup zijn
  generiek — geen hardcoded telling van tabbladen elders in de code of CSS
  die aangepast moest worden.

### Wat je manueel moet testen

1. App starten, tabblad **Openstaand** opent naast Tabel — zelfde stations,
   zelfde kleuren.
2. Een QSO loggen (of importeren) tot een station op **alle getoonde
   banden** groen staat → station verdwijnt uit Openstaand, blijft wél
   zichtbaar in Tabel.
3. Bandfilter instellen op één band: een station dat enkel op die band nog
   openstaat blijft zichtbaar; is die band voor dat station al gewerkt, dan
   verdwijnt het station uit Openstaand (ook al staat een andere band nog
   open, want die is niet zichtbaar met dit filter).
4. Een cel manueel op "excluded" zetten voor alle banden van een station →
   station verdwijnt ook uit Openstaand (niets meer te doen).
5. Alles gewerkt → melding "Niets meer open — alle zichtbare stations zijn
   volledig gewerkt!" verschijnt, met dezelfde "wis filters"-knop als
   elders wanneer een filter actief staat.
6. Taal wisselen (nl/en/fr) — tabnaam en lege-lijst-melding vertalen mee.
7. Cel aanklikken op Openstaand opent hetzelfde detailpaneel als op Tabel.

---

## 2. Release uitrollen — zelfde stappen als v1.3.0

1. **Bestanden uploaden** op GitHub: *Add file > Upload files*, sleep de
   uitgepakte map `app` (met `version.py` en `view/static/`) en
   `RELEASE-NOTES-v1.4.0.md` in het venster — mappenstructuur blijft
   behouden, bestaande bestanden worden overschreven.
   Commit-boodschap: `v1.4.0: tabblad Openstaand`.
2. **Controleer** dat `app/version.py` op GitHub `APP_VERSION = "1.4.0"`
   toont.
3. **Releases > Draft a new release**: tag `v1.4.0` (met de `v`, exact
   gelijk aan `APP_VERSION`) → target `main` → titel `v1.4.0` →
   beschrijving = inhoud van dit bestand → "Set as the latest release"
   aangevinkt → **Publish release**. Niet als draft laten staan.
4. Tabblad **Actions**: workflow "Release" bouwt Windows-installer en
   Linux-pakket (5–10 min) en hangt ze aan de release. Falen de tests, dan
   wordt er niets gepubliceerd.
5. Downloadpagina (`docs/index.html`) hoeft niet aangepast — die haalt de
   nieuwste release dynamisch op.
6. Update testen zoals een clublid: op een pc met de vorige versie,
   **Beheer > Applicatie > Controleer op updates**.
