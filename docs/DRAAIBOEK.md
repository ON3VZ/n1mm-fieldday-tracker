# DRAAIBOEK — van nul tot draaiende tracker (voor dummies)

> Volg dit van boven naar onder, stap voor stap, op je **Windows**-laptop
> (dezelfde waarop N1MM draait). Alles wat je moet typen staat in een
> grijs blok — typ het letterlijk over (of kopieer/plak) in het zwarte
> venster (de "opdrachtprompt"). Duur eerste keer: ± 30 minuten.

---

## STAP 0 — Het zwarte venster openen

Veel stappen gebeuren in de **opdrachtprompt**:

1. Druk op de **Windows-toets**.
2. Typ: `cmd`
3. Druk **Enter**. Er opent een zwart venster. Dat laat je open staan.

---

## STAP 1 — Python installeren (eenmalig)

1. Controleer eerst of je het al hebt. Typ in het zwarte venster:
   ```
   python --version
   ```
   Zie je `Python 3.11.x` of hoger (bv. 3.12)? → **Ga naar stap 2.**
   Zie je een foutmelding of opent de Microsoft Store? → ga verder:
2. Open in je browser: **https://www.python.org/downloads/**
3. Klik op de grote gele knop **Download Python 3.x.x**.
4. Open het gedownloade bestand.
5. ⚠️ **BELANGRIJKSTE STAP:** vink onderaan **"Add python.exe to PATH"**
   aan, **vóór** je verder klikt.
6. Klik **Install Now** en wacht tot het klaar is.
7. **Sluit het zwarte venster en open een nieuw** (stap 0 opnieuw — dit
   moet, anders kent het venster Python nog niet).
8. Controleer: `python --version` → nu moet er een versienummer komen.

---

## STAP 2 — Het project uitpakken (bij elke nieuwe versie)

1. Zorg dat je het zip-bestand hebt. Twee mogelijkheden:
   - **Van mij gekregen** (bv. `n1mm_fieldday_tracker_phase12.zip`), of
   - **Zelf van GitHub gehaald**: op de projectpagina → groene knop
     **Code** → **Download ZIP**.
2. Maak één vaste plek: open Verkenner, ga naar `C:\` en maak daar een map
   **`N1MM-Tracker`**.
3. Rechtsklik op het zip-bestand → **Alles uitpakken…** → kies als doel
   `C:\N1MM-Tracker` → **Uitpakken**.

### ⚠️ Belangrijk: controleer de naam van de map die eruit komt

Elk zip-bestand maakt bij het uitpakken **één extra map** aan. Hoe die
heet, hangt af van waar je de zip vandaan hebt:

| Zip vanwaar? | Map die je krijgt |
|---|---|
| Van mij gekregen | `C:\N1MM-Tracker\n1mm_fieldday_tracker` |
| GitHub → Code → Download ZIP | `C:\N1MM-Tracker\n1mm-fieldday-tracker-main` |
| GitHub → *Source code (zip)* bij een release | `C:\N1MM-Tracker\n1mm-fieldday-tracker-1.0.0` |

GitHub plakt er dus altijd zelf `-main` (of het versienummer) achter. Dat is
normaal en geen fout.

4. **Heet de map niet exact `n1mm_fieldday_tracker`? Hernoem ze dan.**
   Rechtsklik op de map → **Naam wijzigen** → typ:

   ```
   n1mm_fieldday_tracker
   ```

   Doe dit echt even — dan kloppen álle commando's in dit draaiboek, in de
   handleiding en in het testplan zonder dat je ooit iets moet aanpassen.
   Wil je de map toch anders noemen, dan moet je overal hierna
   `n1mm_fieldday_tracker` vervangen door jouw eigen mapnaam.

5. Controle: er bestaat nu `C:\N1MM-Tracker\n1mm_fieldday_tracker\` met
   daarin o.a. de mappen `app`, `docs`, `tests` en het bestand
   `README.md`. Staan `app` en `README.md` er níet in, maar zit er nóg een
   map in? Dan heb je één laag te veel — verplaats de inhoud van die
   binnenste map één niveau omhoog.

> **Nieuwe versie ontvangen?** Pak ze gewoon uit over de oude heen
> (bestanden vervangen: **ja**), en hernoem opnieuw indien nodig. Je
> velddag-gegevens staan op een andere plek en blijven altijd bewaard
> (zie stap 9).

---

## STAP 3 — Eenmalige voorbereiding (venv + pakketten)

In het zwarte venster, regel per regel (na elke regel Enter):

```
cd C:\N1MM-Tracker\n1mm_fieldday_tracker
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

- Krijg je bij de eerste regel *"Het systeem kan het opgegeven pad niet
  vinden"*? Dan heet je map anders dan verwacht → terug naar stap 2.
- Na de derde regel staat er **`(.venv)`** vooraan je prompt. Dat hoort zo.
- De vierde regel downloadt een paar hulppakketten (± 1 minuut).

> Dit hoef je maar **één keer** te doen (en opnieuw na stap 2 als ik ooit
> zeg dat er een nieuw pakket bij kwam — dan volstaat de laatste regel).

---

## STAP 4 — De automatische tests draaien (jouw kwaliteitscontrole)

Dit controleert in ±20 seconden of álles correct werkt op jouw machine.
Doe dit **na elke nieuwe versie die je uitpakt**:

```
cd C:\N1MM-Tracker\n1mm_fieldday_tracker
.venv\Scripts\activate
python -m pytest tests\
```

✅ **Goed:** onderaan staat groen `374 passed` of meer. Het exacte aantal
groeit met elke nieuwe versie — waar het om gaat is dat er **nergens**
`failed` staat.
❌ **Fout:** staat er ergens `failed`? Stuur mij de laatste 20 regels van
het venster, dan los ik het op.

---

## STAP 5 — De deelnemerslijst inladen (eenmalig per velddag)

Zet je Excel (bv. `deelnemerslijst_orig.xlsx`) in
`C:\N1MM-Tracker\` en typ:

```
python -m app.main --import-excel C:\N1MM-Tracker\deelnemerslijst_orig.xlsx
```

✅ Verwacht: `Imported 38 stations (0 issues); bands: ['40m', '80m', '160m']`

(Dit kan ook via het scherm: start de app en klik **Manage** →
deelnemerslijst — zie handleiding hoofdstuk 8.)

---

## STAP 6 — De tracker starten (elke keer)

```
cd C:\N1MM-Tracker\n1mm_fieldday_tracker
.venv\Scripts\activate
python -m app.main
```

- Je browser opent vanzelf op **http://127.0.0.1:8765** met de matrix.
- Vraagt Windows Firewall om toestemming? → **Toegang toestaan** klikken
  (nodig voor de N1MM-ontvangst).
- Stoppen: klik in het zwarte venster en druk **Ctrl+C**.

💡 **Maak het jezelf makkelijk:** maak **in de projectmap zelf**
(`C:\N1MM-Tracker\n1mm_fieldday_tracker\`) een bestand
`START-TRACKER.bat`: rechtsklik → Nieuw → Tekstdocument, plak dit erin,
sla op en hernoem naar `START-TRACKER.bat`.

```bat
@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Virtuele omgeving niet gevonden - doe eerst stap 3.
    pause
    exit /b 1
)
.venv\Scripts\python.exe -m app.main
pause
```

Voortaan is starten één dubbelklik. De regel `cd /d "%~dp0"` betekent
"ga naar de map waar ik zelf in sta" — daardoor blijft dit bestand werken,
ook als de map ooit anders heet of ergens anders staat. Handig: rechtsklik
op het bestand → **Kopiëren naar** → **Bureaublad (snelkoppeling maken)**.

---

## STAP 7 — Testen zonder N1MM (nep-QSO's sturen)

App laten draaien (stap 6) en een **tweede** zwart venster openen:

```
cd C:\N1MM-Tracker\n1mm_fieldday_tracker
.venv\Scripts\activate
python tools\send_test_qso.py ON4BAF/P 3525.19
```

✅ Verwacht: binnen 5 seconden kleurt de cel **ON4BAF / 80m** groen in je
browser, zonder dat je ververst.

Meer proberen:

```
python tools\send_test_qso.py ON4CDZ/P 7020            :: 40m erbij
python tools\send_test_qso.py ON4BAF/P 3525.19 --delete :: weer weg
python tools\send_test_qso.py ON4FA/P 1830 --lookup     :: MOET genegeerd worden
```

---

## STAP 8 — Het testplan (de volledige controle)

- **Waar?** `C:\N1MM-Tracker\n1mm_fieldday_tracker\docs\TESTPLAN.md`
  (openen met Kladblok, of mooi leesbaar op GitHub — zie stap 10).
- **Wat?** Genummerde testen (A1, B1, C1, …) met telkens: wat je doet en
  wat je **moet zien**. Delen A t/m E kan je vandaag al volledig doen,
  deel G is de generale repetitie mét echte N1MM.
- **Hoe rapporteren?** Loop het af met een blad papier ernaast; noteer de
  nummers die **niet** kloppen + wat je zag, en stuur me die lijst. Meer
  heb ik niet nodig.

Volgorde die ik aanraad: **A3 → A1 → B1 → B2 → C1 t/m C8 → D1 t/m D8 →
H1 t/m H7**, en later G1–G6 met N1MM erbij.

---

## STAP 9 — Waar staan mijn gegevens (en de back-up)

Je velddagen staan **niet** in de projectmap maar in:

```
%LOCALAPPDATA%\N1MM Field Day Tracker\
```

(plak dat letterlijk in de adresbalk van Verkenner). Back-up = die map
kopiëren naar een USB-stick. Nieuwe programmaversies raken deze map nooit.

---

## STAP 10 — Broncode op GitHub bewaren (enkel voor de beheerder)

> Dit is **optioneel** en enkel bedoeld voor wie de broncode beheert. Voor
> het draaien van de tracker of het publiceren van de live-pagina heb je
> dit **niet** nodig.

**Gebruik de website, niet git-commando's.** `git pull`/`git push` leidde
in de praktijk tot merge-conflicten die bestanden beschadigen. Upload
daarom handmatig:

1. Ga naar je repo op github.com (bv. `ON3VZ/n1mm-fieldday-tracker`).
2. Klik **Add file → Upload files**.
3. Sleep de projectbestanden en -mappen erin — **behalve** de map `.venv`.
4. Klik **Commit changes**.

Voor een nieuwe versie: dezelfde stappen; gewijzigde bestanden worden
overschreven. Simpel en conflictvrij.

## STAP 11 — Live publiceren voor het publiek

Volledig stappenplan in **handleiding hoofdstuk 13b**: repo `velddag-live`
aanmaken, GitHub Pages aanzetten, fine-grained token maken (enkel Contents
lezen/schrijven op die ene repo!) en in de tracker opslaan. Daarna is het
één knop: **Publish now** — of automatisch elke N minuten.

---

## Welk document waarvoor?

| Bestand (in `docs\`) | Voor wie / wat |
|---|---|
| `HANDLEIDING.md` | **Gebruikers**: installatie, schermen, N1MM, problemen oplossen |
| `TESTPLAN.md` | **Jij als tester**: genummerde controles met verwacht resultaat |
| `ARCHITECTUUR.md` | **Techniek**: visuele diagrammen van hoe alles samenhangt |
| `DRAAIBOEK.md` | **Dit document**: alles van nul, in volgorde |
| `..\README.md` | Kort overzicht voor wie de GitHub-pagina bezoekt |

## Spiekbrief (alles op één rijtje)

```
:: eenmalig
python -m venv .venv

:: elke sessie
cd C:\N1MM-Tracker\n1mm_fieldday_tracker
.venv\Scripts\activate

:: dan naar keuze
python -m pytest tests\                          :: alles testen
python -m app.main                               :: tracker starten
python -m app.main --import-excel LIJST.xlsx     :: lijst importeren
python tools\send_test_qso.py ON4BAF/P 3525.19   :: nep-QSO sturen
git add -A && git commit -m "fase X" && git push :: naar GitHub
```

---

*Draaiboek bijgewerkt bij: blok A. Stap 2 aangevuld met de mapnaam die
GitHub-downloads opleveren (`-main`), na testfeedback van ON4AOL.*
