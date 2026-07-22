# N1MM Field Day Tracker — Testplan

> **Versie:** fase 11. Dit testplan groeit mee met elke oplevering; testen
> voor functies die nog niet gebouwd zijn, staan onderaan als *(gepland)*.
>
> Elke test heeft een nummer, stappen en een **verwacht resultaat**. Vink af
> wat slaagt; noteer bij falen het testnummer + wat je zag.

---

## Deel A — Installatie en basis

**A1. Installatie (Windows)**
Volg hoofdstuk 3 van de handleiding op een propere Windows-pc.
✅ *Verwacht:* `python -m app.main` start zonder fouten; er verschijnt
`Field day : …`, `Web : http://127.0.0.1:8765/` en de browser opent.

**A2. Installatie (Linux, indien beschikbaar)**
Idem via hoofdstuk 4.
✅ *Verwacht:* zelfde gedrag; datamap onder `~/.local/share/N1MM Field Day Tracker/`.

**A3. Automatische testsuite**
`python -m pytest tests/` in de projectmap (venv actief).
✅ *Verwacht:* **321 passed**, 0 failed. Dit is de snelste totaalcontrole
na elke update.

**A4. Eerste start zonder velddag**
Verwijder (of hernoem) de datamap en start de app.
✅ *Verwacht:* melding "No field day found; created 'Field Day <datum>'";
de app start gewoon; matrix is leeg.

**A5. Herstart met bestaande data**
Stop de app (Ctrl+C) en start opnieuw.
✅ *Verwacht:* dezelfde velddag opent; eerder ontvangen QSO's en overrides
staan er nog exact zo bij.

## Deel B — Deelnemerslijst

**B1. Echte Excel importeren**
`python -m app.main --import-excel deelnemerslijst_orig.xlsx`
✅ *Verwacht:* "Imported 38 stations (0 issues); bands: ['40m', '80m', '160m']".

**B2. Matrix toont de lijst**
Start de app en open de matrixview.
✅ *Verwacht:* 38 rijen, in de volgorde van de Excel; kolommen 40m/80m/160m;
categorie onder elke roepnaam; alles wit (niet gewerkt).

**B3. Foute lijst**
Maak een kopie van de Excel; zet in één rij een lege Call en voeg een rij
`ON4BAF` (zonder /P) toe. Importeer.
✅ *Verwacht:* import loopt door; rapport meldt de lege rij (rijnummer) en
de duplicaat-na-normalisatie met verwijzing naar de eerdere rij.

**B4. CSV-variant**
Exporteer de Excel als CSV (puntkomma's) en importeer die.
✅ *Verwacht:* zelfde 38 stations, zelfde banden.

## Deel C — Live QSO's (zonder N1MM, met het testtool)

> Het testtool simuleert N1MM exact: `python tools/send_test_qso.py …`
> Standaard naar `127.0.0.1:12060`.

**C1. QSO binnenkrijgen**
App draait. `python tools/send_test_qso.py ON4BAF/P 3525.19`
✅ *Verwacht:* binnen 5 s (zonder F5!) kleurt de cel ON4BAF/80m groen met ✓.
Live-indicator blijft groen.

**C2. Suffix-tolerantie**
`python tools/send_test_qso.py ON4CDZ 7020` (zónder /P, lijst hééft /P)
✅ *Verwacht:* ON4CDZ/40m wordt groen — de matching negeert de suffix.

**C3. Onbekend station**
`python tools/send_test_qso.py DL1XYZ 3510`
✅ *Verwacht:* er verandert **niets** in de matrix; geen nieuwe rij (BR-03).

**C4. QSO bewerken (replace)**
`python tools/send_test_qso.py ON4BAF/P 3525.19 --replace-call OT5X/P`
✅ *Verwacht:* ON4BAF/80m wordt weer wit, OT5X/80m wordt groen (zelfde ID
verhuist).

**C5. QSO verwijderen**
`python tools/send_test_qso.py OT5X/P 3525.19` gevolgd door
`python tools/send_test_qso.py OT5X/P 3525.19 --delete`

Let op: delete werkt op call+frequentie waarmee gelogd werd — gebruik
dezelfde waarden. (Na C4 staat het QSO op de call uit C4-replace maar met
de frequentie van het origineel; test delete daarom op een vers QSO.)
✅ *Verwacht:* de cel gaat weer open (wit).

**C6. LookupInfo wordt genegeerd**
`python tools/send_test_qso.py ON4KSD/P 1830 --lookup`
✅ *Verwacht:* niets verandert; in de view "Per bron-PC" telt het pakket
wél mee bij de bron (ontvangen), maar er komt geen gewerkte cel bij.

**C7. Rommel crasht niets**
Stuur rommel: `python -c "import socket;s=socket.socket(2,2);s.sendto(b'\\x00garbage',('127.0.0.1',12060))"`
✅ *Verwacht:* app blijft draaien; volgende geldige QSO komt gewoon binnen.

**C8. Meerdere bron-PC's**
Stuur QSO's met `--station PC-160M`, `--station PC-80M`, `--station PC-40M`.
✅ *Verwacht:* view "Per bron-PC" toont drie kaarten, elk LIVE, met correcte
aantallen.

**C9. Freshness / stale**
Stuur 5+ minuten niets (of zet de drempel tijdelijk laag).
✅ *Verwacht:* de bron-kaarten springen naar STALE (rood kader).

**C10. X-QSO**
(Bewerk in het testtool `IsClaimedQso` naar 0, of vraag me om een vlag.)
✅ *Verwacht:* QSO komt binnen maar de cel blijft wit.

## Deel D — Views en filters

**D1. Matrix sticky**
Scroll in de matrix omlaag en opzij (tablet!).
✅ *Verwacht:* kopregel en roepnaamkolom blijven staan; leesbaar in fel licht.

**D2. Celdetail**
Tik op een groene cel.
✅ *Verwacht:* paneel onderaan met tijdstip (UTC), mode, frequentie, bron-PC.
Sluiten met × of Escape.

**D3. Nog te werken**
Open de view; sorteer op band, dan op callsign.
✅ *Verwacht:* enkel open combinaties; teller klopt met de matrix; sortering
wisselt op-/aflopend bij tweede tik.

**D4. Per band**
Kies 80m.
✅ *Verwacht:* voortgangsbalk klopt met de matrixkop; lijst toont per
station status/tijd/bron.

**D5. Per station**
Kies ON4BAF/P.
✅ *Verwacht:* drie banden met status + volledige QSO-lijst (ook een tweede
QSO op dezelfde band verschijnt in de lijst).

**D6. Statistiek**
✅ *Verwacht:* tegels tellen op (gewerkt+open+excluded = totaal); grafiek
"voortgang in de tijd" stijgt met elk QSO; tabellen per band en categorie.

**D7. Filters**
Zoek "ON4B"; filter op categorie; filter op status "gedeeltelijk".
✅ *Verwacht:* matrix én "Nog te werken" volgen de filters; legende blijft.

**D8. Live-indicator bij uitval**
Stop de app terwijl de browser open blijft.
✅ *Verwacht:* indicator wordt binnen ±10 s rood ("No data"); na herstart
van de app herstelt hij vanzelf naar groen.

## Deel E — Overrides en sync (API; knoppen volgen in fase 12/13)

> Tijdelijk via de command line te testen (PowerShell: gebruik `curl.exe`).

**E1. Manual override zetten**
```
curl -X POST http://127.0.0.1:8765/api/override -H "Content-Type: application/json" -d "{\"normalized_callsign\":\"ON4FA\",\"band\":\"160m\",\"override_type\":\"manual_worked\",\"reason\":\"papieren log\",\"set_by\":\"ON6WL\"}"
```
✅ *Verwacht:* cel wordt donkergroen mét ✎; celdetail toont reden en wie.

**E2. Override wint van N1MM**
Zet op een gewerkte (groene) cel `manual_not_worked`.
✅ *Verwacht:* cel wordt oranje ✗ ondanks het bestaande QSO (BR-05).

**E3. Override wissen**
```
curl -X POST http://127.0.0.1:8765/api/override/clear -H "Content-Type: application/json" -d "{\"normalized_callsign\":\"ON4FA\",\"band\":\"160m\"}"
```
✅ *Verwacht:* automatische status geldt weer (groen als er een QSO was,
anders wit).

**E4. Manuele sync**
`curl -X POST http://127.0.0.1:8765/api/sync -d "{}"`
✅ *Verwacht:* JSON-rapport (totaal, matched, per reden geweigerd); de
matrix verandert **niet** (incrementeel en volledig geven hetzelfde — de
kernwaarborg van §9.2).

**E5. Persistentie van overrides**
Zet een override, herstart de app.
✅ *Verwacht:* override staat er nog; wissen na herstart werkt ook.

## Deel F — ADIF (API/CLI; knop volgt)

**F1. ADIF-import**
Exporteer uit N1MM een klein ADIF (of vraag me een testbestand) en
importeer via een Python-oneliner of wacht op de UI-knop.
✅ *Verwacht:* rapport met gelezen/nieuw/duplicaat/buiten periode/onbekend;
matrixcellen kleuren bij.

**F2. Dubbele import**
Importeer hetzelfde bestand nogmaals.
✅ *Verwacht:* alles duplicaat, niets verandert.

## Deel G — Met échte N1MM (de generale repetitie)

**G1. Configuratie** — hoofdstuk 7 van de handleiding volgen (contest
`FDREG1`, Broadcast Data > Contacts, `127.0.0.1:12060`).
✅ *Verwacht:* bij de eerste Windows-firewallvraag "Toegang toestaan"
klikken; view "Per bron-PC" toont de N1MM-pc als LIVE.

**G2. Live loggen** — log een QSO op een deelnemende call.
✅ *Verwacht:* cel kleurt binnen 5 s groen.

**G3. Bewerken in N1MM** — wijzig de callsign van dat QSO.
✅ *Verwacht:* oude cel gaat open, nieuwe cel kleurt (N1MM stuurt delete +
replace; beide verwerkt).

**G4. Verwijderen in N1MM** — wis het QSO.
✅ *Verwacht:* cel gaat weer open.

**G5. Lookup-venster** — zoek een callsign op zónder te loggen.
✅ *Verwacht:* er kleurt níéts (LookupInfo-filter).

**G6. Duurtest** — laat alles 2+ uur draaien met sporadische QSO's.
✅ *Verwacht:* geen geheugen-/stabiliteitsproblemen; teller in
`/api/status` klopt; herstart daarna verliest niets.

## Deel H — Velddagbeheer en knoppen (fase 12)

**H1. Manage-paneel** — klik rechtsboven op *Manage*.
✅ *Verwacht:* paneel schuift open; huidige velddag met ● in de lijst.

**H2. Nieuwe velddag met kopie** — maak "Test 2027" aan, copy-from de
actieve velddag, en open ze.
✅ *Verwacht:* 38 stations en de banden zijn mee; de matrix is **leeg**;
terugwisselen toont de oude data ongewijzigd.

**H3. Banden wijzigen** — vink 20m aan, bewaar.
✅ *Verwacht:* extra kolom verschijnt meteen; QSO's die eerder op 20m
binnenkwamen (bv. via ADIF) kleuren na de automatische herberekening in.

**H4. Re-import met verdwenen station** — verwijder één rij uit een kopie
van de Excel en importeer via het paneel.
✅ *Verwacht:* eerst een waarschuwing met exact die roepnaam; *Cancel*
verandert niets; bevestigen verwijdert het station.

**H5. Override via de cel** — tik op een groene cel, kies *Mark NOT
worked* met reden.
✅ *Verwacht:* cel wordt oranje ✗✎; detail toont de reden; *Clear manual
status* maakt hem weer groen. Herstart de app: de override staat er nog.

**H6. ADIF via de knop** — importeer een .adi-bestand tweemaal.
✅ *Verwacht:* eerste keer rapport met nieuw>0; tweede keer alles duplicaat.

**H7. Foutafhandeling** — maak een velddag met einde vóór start.
✅ *Verwacht:* nette foutmelding in het paneel, geen crash.

## Deel I — *(gepland, per komende fase)*

- **Fase 13**: settings-UI (taal, UDP, kleuren, strict matching — met test:
  strict aan + hersync verandert de matrix zoals verwacht)
- **Fase 15**: CSV-export (opent in Excel, juiste kolommen) en PDF-export
  (landschap, matrix gesplitst bij veel banden)
- **Fase 16**: publicatie naar GitHub Pages (token in keyring, publieke
  pagina ververst binnen 30 s, opmerkingen weggelaten indien ingesteld)
- **Fase 17**: taalwissel en/nl/fr/es in de webview
- **Fase 18**: .exe-build (start zonder Python; Defender-melding wegklikken)
- **Fase 19**: het volledige end-to-end-scenario uit §11.1 van de spec, in
  één doorlopende sessie

---

*Testplan bijgewerkt bij: fase 12.*
