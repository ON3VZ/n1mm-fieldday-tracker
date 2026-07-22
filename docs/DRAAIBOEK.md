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

1. Je hebt van mij een bestand zoals `n1mm_fieldday_tracker_phase12.zip`.
   Bewaar het in je **Downloads**.
2. Maak één vaste plek: open Verkenner, ga naar `C:\` en maak daar een map
   **`N1MM-Tracker`**.
3. Rechtsklik op het zip-bestand → **Alles uitpakken…** → kies als doel
   `C:\N1MM-Tracker` → **Uitpakken**.
4. Controleer: er bestaat nu `C:\N1MM-Tracker\n1mm_fieldday_tracker\` met
   daarin o.a. de mappen `app`, `docs`, `tests` en het bestand `README.md`.

> **Nieuwe versie ontvangen?** Pak ze gewoon uit over de oude heen
> (bestanden vervangen: **ja**). Je velddag-gegevens staan op een andere
> plek en blijven altijd bewaard (zie stap 9).

---

## STAP 3 — Eenmalige voorbereiding (venv + pakketten)

In het zwarte venster, regel per regel (na elke regel Enter):

```
cd C:\N1MM-Tracker\n1mm_fieldday_tracker
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

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

✅ **Goed:** onderaan staat groen `326 passed` (het aantal groeit per fase).
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

💡 **Maak het jezelf makkelijk:** maak in `C:\N1MM-Tracker\` een bestand
`START-TRACKER.bat` (rechtsklik → Nieuw → Tekstdocument, plak de drie
regels hierboven erin, sla op en hernoem naar `.bat`). Voortaan is starten
één dubbelklik.

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

## STAP 10 — Alles op GitHub zetten

### 10a. Git installeren (eenmalig)

1. Download **https://git-scm.com/download/win** en installeer (overal
   gewoon *Next*).
2. Nieuw zwart venster; controleer met `git --version`.

### 10b. De eerste keer uploaden

Je hebt op github.com al de repo **`n1mm-fieldday-tracker`** aangemaakt.
Typ (vervang `JOUWNAAM` door je GitHub-gebruikersnaam):

```
cd C:\N1MM-Tracker\n1mm_fieldday_tracker
git init
git branch -M main
git remote add origin https://github.com/JOUWNAAM/n1mm-fieldday-tracker.git
git add -A
git commit -m "fase 12"
git push -u origin main
```

Bij de eerste push opent een venstertje om in te loggen bij GitHub —
gewoon inloggen in de browser die opent.

### 10c. Elke nieuwe fase uploaden (3 regels)

Na het uitpakken van een nieuwe zip (stap 2) en de testcontrole (stap 4):

```
cd C:\N1MM-Tracker\n1mm_fieldday_tracker
git add -A
git commit -m "fase 13"
git push
```

Zo krijg je op GitHub één nette versie per fase, en **daar zie je de
architectuurtekeningen** uit `docs/ARCHITECTUUR.md` als echte diagrammen.

---

## STAP 11 — N1MM aankoppelen (de dag zelf)

Volledig uitgelegd in de **handleiding hoofdstuk 7**; samengevat:

1. N1MM: `Config > Config Ports, Mode Control, Audio, Other… >`
   tabblad **Broadcast Data**.
2. Vink **Contacts** aan (níét Lookup).
3. Bestemming: `127.0.0.1:12060`
4. Contest: **FDREG1**. Klaar — log een test-QSO en zie de cel kleuren.

---

## STAP 12 — Live publiceren voor het publiek

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

*Draaiboek bijgewerkt bij: fase 16.*
