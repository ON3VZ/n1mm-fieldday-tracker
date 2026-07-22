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

**A6. Crash-simulatie (belangrijk vóór de velddag!)**
Laat de app draaien met enkele QSO's in de matrix. Sluit het zwarte
venster met de **✕** (dat is een harde kill, geen nette afsluiting).
Start de app opnieuw.
✅ *Verwacht:* binnen enkele seconden staat exact dezelfde matrix er weer,
inclusief manuele statussen. Er gaat níéts verloren — elk QSO wordt bij
ontvangst meteen bewaard. (Geverifieerd met kill -9: hersteltijd < 1 s.)

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

**D8b. Filters wissen**
Zoek op een onbestaande roepnaam zodat de matrix leeg is.
✅ *Verwacht:* melding "No stations match" mét een knop **Clear all
filters**; één tik en alle 38 rijen staan er weer. Ook na een re-import
van de lijst mag een oud categorie-filter nooit blijven "plakken".

**D9. Meldingen als popup**
Doe een ADIF-import of zet een override.
✅ *Verwacht:* de melding verschijnt als **popup bovenaan het scherm**
(geen scrollen nodig) en verdwijnt vanzelf na enkele seconden. Een import
met 0 nieuwe QSO's toont een oranje popup mét de reden — bv. de tip dat de
QSO's buiten de velddagperiode vallen.

**D8. Live-indicator bij uitval**
Stop de app terwijl de browser open blijft.
✅ *Verwacht:* indicator wordt binnen ±10 s rood ("No data"); na herstart
van de app herstelt hij vanzelf naar groen.

## Deel E — Overrides en sync (via de knoppen)

**E1. Manual override zetten**
Tik in de matrix op een lege cel (bv. ON4FA / 160m) en kies **Mark
worked**, vul als reden "papieren log" in.
✅ *Verwacht:* popup "Done."; cel wordt donkergroen mét ✎; celdetail toont
de reden.

**E2. Override wint van N1MM**
Tik op een grőene (gewerkte) cel en kies **Mark NOT worked**.
✅ *Verwacht:* cel wordt oranje ✗✎ ondanks het bestaande QSO (BR-05).

**E3. Override wissen**
Tik op de cel uit E2 en kies **Clear manual status**.
✅ *Verwacht:* de automatische status geldt weer — **groen**, want het
N1MM-QSO bestaat nog. (Wis je de override van E1 op een cel zónder QSO,
dan wordt die weer wit.) *Servermatig geverifieerd: override → clear →
`worked_by_n1mm`.*

**E4. Manuele sync**
Manage → **Full resync now**.
✅ *Verwacht:* popup met het rapport (x van y QSO's tellen); de matrix
verandert **niet** — incrementeel en volledig geven hetzelfde (§9.2).

**E5. Persistentie**
Zet een override, herstart de app.
✅ *Verwacht:* override staat er nog; wissen na herstart werkt ook.

> Liever via de command line? Gebruik in PowerShell **`curl.exe`** (niet
> `curl`, dat is daar een alias die de JSON-quotes breekt) of gewoon cmd.

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

## Deel I — Instellingen en huisstijl (fase 13)

**I1. WLD-stijl** — open de pagina.
✅ *Verwacht:* donkerblauwe (navy) topbalk met het witte **WLD**-lettermerk
en teal scheidingsstreepje; teal accenten (live-stip, actieve tab,
voortgangsbalkjes); oranje foutmeldingen.

**I2. Kleuren wijzigen** — Manage → Settings → kies voor "Worked (N1MM)"
een andere kleur en bewaar.
✅ *Verwacht:* alle groene cellen en de legende nemen meteen de nieuwe
kleur aan; na herstart staat ze er nog.

**I3. Strict matching** — vink strict aan en bewaar.
✅ *Verwacht:* de matrix herrekent meteen; rijen tonen nu de volledige
roepnaam mét /P; een eerder los gematcht QSO zonder /P telt niet meer.
Uitvinken herstelt alles.

**I4. UDP-adres wijzigen** — zet de poort op 12061 en bewaar.
✅ *Verwacht:* melding dat de ontvanger herstart is; het testtool met
`--port 12061` komt binnen, op 12060 niet meer. Zet terug op 12060.

**I5. Freshness** — zet "stale after" op 10 s en stuur even niets.
✅ *Verwacht:* bron-PC's worden na 10 s STALE; na een nieuw pakket weer
LIVE.

**I6. Taal** — kies NL en bewaar.
✅ *Verwacht:* instelling wordt onthouden (zichtbaar na herladen); teksten
blijven Engels tot de vertalingen er zijn (fase 17).

## Deel J — Station toevoegen, afsluiten, export (fase 15)

**J1. Station toevoegen** — klik **+ Station** in de filterbalk, vul
`ON9TST/P` in en bewaar.
✅ *Verwacht:* popup "Station added."; nieuwe rij onderaan de matrix; blijft
staan na her-import van de Excel (manuele stations verdwijnen nooit).

**J2. Duplicaat geweigerd** — voeg `ON4BAF` toe (lijst heeft `ON4BAF/P`).
✅ *Verwacht:* oranje popup dat dit hetzelfde station is.

**J2b. Station verwijderen** — tik op een cel van een station en kies
*Remove this station*; bevestig.
✅ *Verwacht:* bevestiging gevraagd; station verdwijnt uit de matrix. Log
je nadien een QSO voor die roepnaam en voeg je het station weer toe, dan
staat het contact er weer (QSO's blijven bewaard).

**J3. Velddag afsluiten** — Manage → Close field day → bevestig.
✅ *Verwacht:* oranje **CLOSED**-badge bovenaan; testtool-QSO's komen niet
meer binnen; celklik toont geen override-knoppen; ADIF-import geeft een
nette weigering. Herstart de app: nog steeds CLOSED.

**J4. Heropenen** — Manage → Reopen field day → bevestig.
✅ *Verwacht:* badge weg; een test-QSO komt meteen weer binnen.

**J5. PDF-export** — Manage → Export PDF.
✅ *Verwacht:* download opent; A4 **liggend**; WLD-kopband; matrix past op
de paginabreedte; kleuren + letters (X/M/m/–) kloppen met het scherm; bij
38 stations loopt de tabel door op pagina 2 met herhaalde kopregel.

**J6. CSV-export** — Manage → Export CSV; open in Excel.
✅ *Verwacht:* dubbelklik opent correct (puntkomma's, accenten ok); één
rij per station+band; gewerkte rijen tonen bron-PC, mode, frequentie en
UTC-tijd.

**J7. Exportmap** — Settings → Export folder instellen op bv.
`C:\N1MM-Tracker\exports`, opnieuw exporteren.
✅ *Verwacht:* kopieën verschijnen in die map.

## Deel K — Publicatie naar GitHub Pages (fase 16)

**K1. Opzet** — doorloop stap 1–4 van handleiding hoofdstuk 13b (repo
`velddag-live`, Pages aan, fine-grained token met enkel Contents R/W op
die ene repo, token opslaan in de tracker).
✅ *Verwacht:* na *Store token* staat er "(token configured)"; de publieke
URL verschijnt onder de knoppen.

**K2. Eerste publicatie** — klik **Publish now**.
✅ *Verwacht:* popup "Published: 4 uploaded, 0 unchanged."; in de repo op
github.com staan `snapshot.json`, `index.html`, `app.js`, `style.css`.

**K3. Publieke pagina** — open de Pages-URL (evt. 1–2 min wachten bij de
allereerste keer) op je gsm.
✅ *Verwacht:* dezelfde matrix in WLD-stijl, **zonder** Manage-knop en
zonder override-knoppen; indicator zegt "Public view"; pagina ververst
zichzelf (log een QSO, publiceer, en zie hem binnen ±30 s verschijnen
zonder F5).

**K4. Privacy** — zet een opmerking bij een station, publiceer, en bekijk
`snapshot.json` in de repo.
✅ *Verwacht:* de opmerking staat er **niet** in (standaard weggelaten);
met het vinkje aan wél.

**K5. Ongewijzigd overslaan** — klik tweemaal kort na elkaar Publish now.
✅ *Verwacht:* tweede keer "0–1 uploaded, 3+ unchanged" (statische
bestanden worden geskipt).

**K6. Automatisch** — interval op 2 minuten, vinkje aan, opslaan. Log
QSO's en wacht.
✅ *Verwacht:* de publieke pagina volgt vanzelf, zonder klikken.

**K7. Offline-gedrag** — trek de internetkabel uit en klik Publish now.
✅ *Verwacht:* nette oranje foutpopup na de automatische herpogingen; de
tracker zelf blijft gewoon doorwerken; met internet terug lukt het weer.

## Deel L — Verwijderen en export/import van velddagen (blok B)

**L1. Exporteren** — Manage → Velddagen → klik ⭳ bij een velddag.
✅ *Verwacht:* er wordt een `.fdtracker`-bestand gedownload.

**L2. Importeren op dezelfde of andere pc** — klik "Import field day from
file…" en kies dat bestand.
✅ *Verwacht:* popup "Field day imported: … (x QSOs, y stations)"; een
**nieuwe** velddag verschijnt in de lijst (de oude blijft ongewijzigd);
na *Open* staat exact dezelfde matrix er, inclusief QSO's en manuele
statussen.

**L3. Dubbel importeren** — importeer hetzelfde bestand nog eens.
✅ *Verwacht:* opnieuw een nieuwe velddag; niets wordt overschreven.

**L4. Verwijderen met beveiliging** — klik 🗑 bij een niet-actieve velddag.
✅ *Verwacht:* je moet het woord **DELETE** typen; iets anders → melding
"not deleted"; DELETE → velddag en al zijn logs zijn weg.

**L5. Actieve velddag beschermd** — merk op dat de actieve velddag (met ●)
géén 🗑-knop heeft.
✅ *Verwacht:* je kan de actieve niet verwijderen; wissel eerst naar een
andere velddag.

**L6. Testdata opruimen** — maak een testvelddag, log wat, en verwijder ze
daarna via L4.
✅ *Verwacht:* de testdata is volledig verdwenen uit de lijst en van schijf.

## Deel M — Publieke pagina per velddagstatus (blok C)

**M1. Live** — actieve velddag binnen de periode, publiceer.
✅ *Verwacht:* de publieke pagina toont de live matrix; "updated … ago"
verwijst naar het publicatiemoment, niet naar het herladen.

**M2. Aankomend** — zet de start van de actieve velddag in de toekomst,
publiceer, open de publieke pagina.
✅ *Verwacht:* "Field day starts soon" met datum en een aftelling; geen
matrix of deelnemers zichtbaar; ook niet in het snapshot-bestand.

**M3. Geen actieve velddag** — sluit de actieve velddag af, publiceer.
✅ *Verwacht:* "No active field day"; staat er een velddag met een
toekomstige startdatum, dan verschijnt die als "Next planned: …".

**M4. Verlopen** — zet het einde van de actieve velddag meer dan 7 dagen in
het verleden, publiceer.
✅ *Verwacht:* "This field day has ended"; geen resultaten meer zichtbaar
en geen data in het snapshot-bestand.

**M5. Offline** — trek de internetverbinding uit en klik Publish now.
✅ *Verwacht:* nette melding dat er geen verbinding is; geen herhaalstorm;
de tracker blijft lokaal werken.

## Deel N — *(gepland, per komende fase)*

- **Fase 17**: taalwissel en/nl/fr/es in de webview
- **Fase 18**: .exe-build (start zonder Python; Defender-melding wegklikken)
- **Fase 19**: het volledige end-to-end-scenario uit §11.1 van de spec, in
  één doorlopende sessie

---

*Testplan bijgewerkt bij: blok C.*
