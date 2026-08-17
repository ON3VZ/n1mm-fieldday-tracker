# N1MM Field Day Tracker — Handleiding

> **Versie:** fase 1 (projectsetup). Deze handleiding groeit mee met elke
> oplevering. Onderdelen die nog niet beschikbaar zijn, staan gemarkeerd als
> *(volgt in een latere fase)*.

---

## Inhoud

1. [Wat is dit programma?](#1-wat-is-dit-programma)
2. [Wat heb je nodig?](#2-wat-heb-je-nodig)
3. [Installatie op Windows](#3-installatie-op-windows)
4. [Installatie op Linux](#4-installatie-op-linux)
5. [Het programma starten](#5-het-programma-starten)
6. [Waar staan mijn gegevens?](#6-waar-staan-mijn-gegevens)
7. [N1MM Logger+ instellen](#7-n1mm-logger-instellen) *(volgt)*
8. [Een velddag aanmaken](#8-een-velddag-aanmaken) *(volgt)*
9. [Deelnemerslijst importeren](#9-deelnemerslijst-importeren) *(volgt)*
10. [De tabel gebruiken](#10-de-tabel-gebruiken) *(volgt)*
11. [ADIF-import](#11-adif-import) *(volgt)*
12. [Exporteren naar CSV en PDF](#12-exporteren-naar-csv-en-pdf) *(volgt)*
13. [Publiceren naar GitHub Pages](#13-publiceren-naar-github-pages) *(volgt)*
14. [Hoe werkt het technisch?](#14-hoe-werkt-het-technisch)
15. [Wat als de app crasht?](#15-wat-als-de-app-crasht-tijdens-de-velddag)
16. [Problemen oplossen](#16-problemen-oplossen)

---

## 1. Wat is dit programma?

De N1MM Field Day Tracker draait **naast** N1MM Logger+ tijdens een velddag.
N1MM blijft de officiële logger — je logt daar zoals altijd. De tracker
luistert mee en toont in een overzichtelijke **matrix** welke deelnemende
stations op welke banden al gewerkt zijn, en welke nog open staan.

Het vervangt de Excel die tot nu toe handmatig werd bijgehouden.

Belangrijk om te weten:

- Alles werkt **offline**. Enkel het (optionele) publiceren van de publieke
  webpagina vereist internet.
- Er wordt **niets geïnstalleerd** buiten het programma zelf: geen database,
  geen server, geen account.
- Alle gegevens staan in gewone bestanden op je eigen laptop.

## 2. Wat heb je nodig?

- Een laptop met **Windows** of **Linux** — dezelfde laptop waarop N1MM draait.
- **Python 3.11 of nieuwer** (enkel tijdens de ontwikkelfase; later komt er
  een kant-en-klare `.exe` voor Windows waarvoor je geen Python nodig hebt).
- De deelnemerslijst als Excel- (`.xlsx`) of CSV-bestand.

### Heb ik al Python?

Open een opdrachtprompt (Windows: druk op de Windows-toets, typ `cmd`,
Enter) of terminal (Linux) en typ:

```
python --version
```

Zie je `Python 3.11.x` of hoger, dan ben je klaar. Zie je een foutmelding of
een lager versienummer, volg dan de installatiestap hieronder.

## 3. Installatie op Windows

### Stap 1 — Python installeren (indien nodig)

1. Ga naar <https://www.python.org/downloads/> en download de nieuwste
   Python 3-versie.
2. Start het installatieprogramma.
3. **Belangrijk:** vink onderaan **"Add python.exe to PATH"** aan vóór je op
   *Install Now* klikt.
4. Controleer na afloop met `python --version` in een **nieuw** cmd-venster.

### Stap 2 — Projectmap aanmaken

1. Pak het zip-bestand uit, bijvoorbeeld naar `C:\N1MM-Tracker\`.
2. **Controleer de naam van de map die eruit komt.** Elk zip-bestand maakt
   één extra map aan, en de naam verschilt naargelang de bron:

   | Zip vanwaar? | Map die je krijgt |
   |---|---|
   | Rechtstreeks geleverd | `n1mm_fieldday_tracker` |
   | GitHub → Code → Download ZIP | `n1mm-fieldday-tracker-main` |
   | GitHub → *Source code (zip)* bij een release | `n1mm-fieldday-tracker-1.0.0` |

3. Heet de map niet exact `n1mm_fieldday_tracker`, **hernoem ze dan zo**
   (rechtsklik → Naam wijzigen). Daarna kloppen alle padcommando's in deze
   handleiding en in het draaiboek zonder aanpassing.
4. Controle: `C:\N1MM-Tracker\n1mm_fieldday_tracker\` bevat o.a. `app\`,
   `tests\` en `README.md`. Zit daar in plaats daarvan nóg een map in, dan
   heb je één laag te veel — verplaats de inhoud één niveau omhoog.

### Stap 3 — Virtuele omgeving aanmaken (eenmalig)

Een virtuele omgeving is een afgeschermd hoekje waarin het programma zijn
hulppakketten bewaart, zonder iets aan de rest van je pc te veranderen.

Open cmd en typ:

```
cd C:\N1MM-Tracker\n1mm_fieldday_tracker
python -m venv .venv
```

### Stap 4 — Hulppakketten installeren (eenmalig)

```
.venv\Scripts\activate
pip install -r requirements.txt
```

Je ziet nu `(.venv)` vooraan je prompt staan — dat is normaal en goed.

## 4. Installatie op Linux

```bash
# Python 3.11+ installeren indien nodig (Debian/Ubuntu):
sudo apt install python3 python3-venv

# Projectmap: pak de zip uit, bv. naar ~/n1mm-tracker
cd ~/n1mm-tracker/n1mm_fieldday_tracker

# Virtuele omgeving aanmaken (eenmalig)
python3 -m venv .venv

# Activeren en hulppakketten installeren (eenmalig)
source .venv/bin/activate
pip install -r requirements.txt
```

## 5. Het programma starten

Telkens je het programma wil starten:

**Windows:**

```
cd C:\N1MM-Tracker\n1mm_fieldday_tracker
.venv\Scripts\activate
python -m app.main
```

**Linux:**

```bash
cd ~/n1mm-tracker/n1mm_fieldday_tracker
source .venv/bin/activate
python -m app.main
```

Bij het starten opent automatisch je webbrowser met de tracker
(`http://127.0.0.1:8765`). In het terminalvenster zie je de actieve
velddag, het aantal stations en of de UDP-ontvangst luistert. Stoppen doe
je met **Ctrl+C** in dat venster.

Handige opties:

```
python -m app.main --import-excel deelnemerslijst.xlsx   # lijst importeren
python -m app.main --no-browser                          # zonder browser
```

Bij de allereerste start (nog geen velddag) maakt het programma er
automatisch één aan; nette velddagbeheer-schermen volgen in een latere
fase.

## 6. Waar staan mijn gegevens?

Al je velddagen, instellingen en logs staan **buiten** de programmamap, zodat
je het programma kan bijwerken zonder gegevens te verliezen:

- **Windows:** `%LOCALAPPDATA%\N1MM Field Day Tracker\`
  (typ dat pad letterlijk in de adresbalk van Verkenner)
- **Linux:** `~/.local/share/N1MM Field Day Tracker/`

Elke velddag krijgt daarin zijn eigen submap onder `fielddays\`. Een back-up
maken = die map kopiëren naar een USB-stick.

## 7. N1MM Logger+ instellen

De tracker draait op **dezelfde laptop als N1MM**. Zo stel je N1MM in:

1. Open in N1MM: `Config > Config Ports, Mode Control, Audio, Other…`
2. Ga naar het tabblad **Broadcast Data**.
3. Vink **Contacts** aan. (N1MM stuurt dan een berichtje bij elk gelogd,
   bewerkt én verwijderd QSO.)
4. Vul als bestemming in: `127.0.0.1:12060`
5. Klik OK. De contest in N1MM is **`FDREG1`**.

**Belangrijk — vink *Lookup* NIET aan.** Dat stuurt berichten die op QSO's
lijken maar het niet zijn (ze vertrekken al bij het opzoeken van een
roepnaam). De tracker herkent en negeert ze, maar aanvinken heeft geen nut.

### Meerdere N1MM-computers

- **Netwerk-modus** (alle PC's delen één log): vink op **precies één**
  station ook **All Computers** aan. Dat ene station stuurt dan álle QSO's
  van het hele netwerk door. Meerdere stations met deze optie tegelijk
  veroorzaakt een pakketstorm — niet doen.
- **Losse logs per PC**: elke PC stuurt zelf naar het IP-adres van de
  trackerlaptop, bv. `192.168.1.50:12060`. Zet dan in de tracker-settings
  de UDP-host op `0.0.0.0` (standaard staat die veilig op `127.0.0.1` en
  komt alleen verkeer van de eigen laptop binnen).

### Werkt de verbinding?

De tracker toont per bron-PC wanneer het laatste pakket binnenkwam. Komt er
niets binnen, zie hoofdstuk 14 (Problemen oplossen).

## 8. Een velddag aanmaken en beheren

Klik rechtsboven op **Manage**. In het paneel kan je:

- **Velddagen**: de lijst van alle velddagen; klik *Open* om te wisselen.
  Er is altijd precies één velddag actief. **N1MM schrijft altijd naar de
  actieve velddag** — binnenkomende QSO's komen dus in de velddag die op
  dat moment open staat. Een afgesloten (CLOSED) velddag negeert
  binnenkomende QSO's.
- **Nieuwe velddag**: naam + start en einde (in jouw lokale tijd; het
  programma rekent zelf om naar UTC). Kies optioneel **"Copy from"** om
  stations, banden en instellingen over te nemen van een bestaande velddag
  — de matrix start dan toch leeg, QSO's en manuele statussen gaan nooit mee.
- **Huidige velddag bewerken**: naam, locatie, event-callsign, club,
  periode en de **te volgen banden** (vinkjes).
- **Deelnemerslijst**: importeer de Excel of CSV. Importeer je een nieuwe
  versie terwijl er al een lijst is, en ontbreken daarin stations, dan
  toont het programma **eerst welke** en vraagt het bevestiging voor het ze
  verwijdert. Handmatig toegevoegde stations verdwijnen nooit vanzelf, en
  manuele statussen blijven staan.
- **ADIF import**: het vangnet uit hoofdstuk 11, nu als knop, met rapport.
- **Full resync**: herrekent alles vanaf nul — het resultaat hoort altijd
  identiek te zijn aan wat er al stond.

### Zelf een status zetten (manual override)

Tik in de matrix op een cel en kies onderaan: **Mark worked**, **Mark NOT
worked** of **Exclude**, eventueel met een reden ("papieren log"). Manuele
statussen winnen áltijd van wat N1MM zegt en zijn herkenbaar aan het
✎-symbool. **Clear manual status** herstelt de automatische status. Dit
kan alleen op de lokale versie — de publieke pagina is alleen-lezen.

## 9. Deelnemerslijst importeren

*(het importeren zelf gebeurt via het programma en volgt in fase 12; het
bestandsformaat ligt nu al vast)*

### Welk bestand heb ik nodig?

Een Excel-bestand (`.xlsx`) of CSV-bestand met **één rij per deelnemend
station** en een **kopregel** met kolomnamen. De bestaande deelnemerslijst
(`deelnemerslijst_orig.xlsx`) werkt zonder aanpassingen.

### Kolommen

| Kolomnaam (kop) | Verplicht? | Betekenis |
|---|---|---|
| `Call` (of `Callsign`, `Roepnaam`) | **Ja** | De roepnaam, bv. `ON4BAF/P` |
| `categorie` (of `Category`) | **Ja** | Deelnamecategorie, bv. `Restricted 12h` |
| `sectie` (of `Section`) | **Ja** | UBA-sectie, bv. `RST` |
| Bandkolommen: `40M`, `80M`, `160M`, … | **Ja**, minstens één | Zie hieronder |
| `Opm.` (of `Opmerking`, `Remarks`) | Nee | Vrije opmerking |
| `Naam` (of `Name`) | Nee | Naam operator/station |
| `Club` | Nee | Clubnaam |
| Andere kolommen (bv. `Nummer`) | — | Worden genegeerd |

Hoofdletters, kleine letters en extra spaties in de kopjes maken niet uit,
en de **volgorde van de kolommen maakt niet uit**.

### Vast formaat: wat als het bestand niet klopt?

Ontbreekt één van de verplichte kolommen, dan wordt het bestand **in zijn
geheel geweigerd** — er wordt niets half geïmporteerd en je bestaande lijst
blijft ongewijzigd. Op het scherm verschijnt dan een kader met:

- welke kolom(men) ontbreken
- welke kopjes er wél in jouw bestand stonden
- de volledige vereiste indeling, met voorbeeldwaarden

Zet de ontbrekende kolom erbij (een lege kolom met het juiste kopje volstaat
om aan het formaat te voldoen) en importeer opnieuw.

### Bandkolommen

Kolommen met een bandnaam als kop (`40M`, `80M`, `160M`, `2m`, `70cm`, …)
worden gebruikt als **voorstel voor de te volgen banden** van de velddag.
De *inhoud* van die cellen wordt bewust genegeerd: de matrix start bij een
nieuwe velddag altijd leeg, ook al stonden er kruisjes in de Excel.

### Wat als er fouten in de lijst staan?

De import stopt nooit op een foute rij. Na afloop krijg je een rapport met
per probleemrij het rijnummer en de reden, bv.:

- rij zonder roepnaam
- een waarde die geen roepnaam kan zijn
- **dubbele stations**: staan `ON4BAF` en `ON4BAF/P` allebei in de lijst,
  dan wordt de tweede overgeslagen en gemeld (het is hetzelfde station)

### CSV-formaat

Zelfde kolomlogica én dezelfde verplichte kolommen als Excel — een CSV is
geen achterpoortje om de formaatcontrole te omzeilen. Zowel komma's als
puntkomma's als scheidingsteken worden automatisch herkend (een CSV die je
uit Belgische Excel exporteert, gebruikt puntkomma's — dat werkt gewoon).

## 10. De tabel gebruiken

De webpagina toont bovenaan de velddagnaam, de periode, het
**versienummer** van de applicatie en een **live-indicator**. Dat
versienummer staat er zodat je bij een probleem meteen kan zeggen met
welke versie je werkt — het reist ook mee naar de publieke pagina, die dus
de versie toont die de pagina gemaakt heeft. De pagina ververst zichzelf automatisch (elke paar
seconden lokaal, elke 30 seconden op de publieke pagina) — je hoeft nooit
op F5 te duwen. Wordt de indicator rood, dan komt er geen data meer binnen.

Er zijn zes weergaven, via de tabbladen bovenaan:

1. **Tabel** — het hoofdscherm. Rijen = stations, kolommen = banden. De
   kolomkoppen tonen per band een klein voortgangsbalkje. Kopregel en
   roepnaamkolom blijven staan bij het scrollen. Tik op een cel voor de
   details (tijdstip, mode, frequentie, bron-PC).
2. **Nog te werken** — de platte lijst van alle open station+band-
   combinaties. Sorteer door op een kolomkop te tikken. Dít is de lijst
   voor tijdens de nacht.
3. **Per band** — kies een band, zie de voortgangsbalk en alle stations.
4. **Per station** — kies een station, zie alle banden en alle QSO's.
5. **Per bron-PC** — welke computer heeft wat gewerkt, wanneer het laatste
   pakket binnenkwam, en of de verbinding **LIVE** of **STALE** is.
6. **Statistiek** — samenvattende cijfers, voortgang in de tijd, en
   tabellen per band en per categorie.

Bovenaan kan je altijd **filteren**: zoeken op roepnaam, op status (gewerkt
/ niet gewerkt / gedeeltelijk), band, categorie en sectie.

**Op een smartphone** staan de filters dichtgeklapt achter de knop
**Filters ▾**; tik erop om ze open te vouwen. Staat er een blauw bolletje
naast, dan is er een filter actief en zie je dus niet alle stations. De
tabbladen staan op één rij die je horizontaal kan schuiven, en de tabel
past zich aan de schermhoogte aan, zodat het eerste station altijd
leesbaar is. Op pc en tablet verandert er niets: daar blijven de filters
gewoon zichtbaar staan.

> Op een smartphone zit de knop **Station toevoegen** in het filterpaneel;
> vouw dat dus eerst open. (Die knop bestaat enkel op de lokale versie.)

Manueel gezette statussen zijn herkenbaar aan het **✎-symbool** in de
celhoek — ook zonder kleuren te zien. De betekenis van elke kleur staat in
de legende onderaan.

*(cellen aanklikken om zelf een status te zetten — de "manual override" —
werkt vanaf de volgende fase, enkel op de lokale versie; de publieke pagina
is altijd alleen-lezen)*

## 11. ADIF-import

De ADIF-import is het **vangnet** voor QSO's die niet live binnenkwamen:
een PC die offline stond, de tracker die te laat gestart werd, of een
station dat pas 's avonds zijn log komt afgeven.

*(de knop hiervoor verschijnt in een latere fase; dit werkt eronder:)*

1. Exporteer in N1MM het log als ADIF-bestand (`.adi`).
2. Importeer dat bestand in de tracker.
3. Je krijgt een **rapport**: hoeveel records gelezen, hoeveel nieuw,
   hoeveel duplicaten (al gekend, bv. al live binnengekomen), hoeveel
   buiten de velddagperiode vielen, en hoeveel van niet-deelnemende
   stations kwamen (die worden genegeerd).

Je kan hetzelfde bestand gerust twee keer importeren: alles wordt dan als
duplicaat herkend en er verandert niets. Dubbel tellen kan sowieso niet —
één QSO of tien QSO's op dezelfde roepnaam en band geeft gewoon "gewerkt".

## 12. Exporteren naar CSV en PDF

Manage → **Export**:

- **Export PDF** — de volledige matrix op **A4 liggend**, passend op de
  paginabreedte, in WLD-stijl: kopband met logo, velddaggegevens,
  samenvattende cijfers, legende en de matrix met de statuskleuren. Naast
  kleur staat in elke cel ook een letter (X = gewerkt, M = manueel
  gewerkt, m = manueel niet gewerkt, – = uitgesloten) zodat de afdruk ook
  in zwart-wit leesbaar blijft. Bij heel veel banden splitst de matrix
  automatisch over meerdere pagina's; lange lijsten lopen door met
  herhaalde kopregel.
- **Export CSV** — één rij per station+band met alle details (status,
  bron-PC, mode, frequentie, tijdstip, manuele status, opmerkingen).
  Opent rechtstreeks correct in Belgische Excel.

Beide downloads verschijnen in je browser én er wordt een kopie bewaard in
de exportmap (instelbaar in Settings; standaard de `exports\`-map van de
velddag).

### Station manueel toevoegen (+)

Rechts in de filterbalk staat **+ Station**. Die opent het paneel bij
"Station handmatig toevoegen": roepnaam (verplicht) plus optioneel
categorie, sectie en opmerking. Handig voor een station dat op de dag zelf
nog aansluit. Manueel toegevoegde stations verdwijnen nooit bij een
her-import van de Excel.

De **categorie kies je uit een keuzelijst** in plaats van ze in te tikken.
Dat is er niet voor de sierlijkheid: een tikfout in een categorie maakt
stilzwijgend een tweede categorie aan, waardoor de statistiek per
categorie in twee splitst en het filter twee bijna identieke regels toont.
Staat de gewenste categorie er niet bij, kies dan **Andere… (zelf
intypen)** en typ ze voluit — of voeg ze toe aan de vaste lijst in de
instellingen (zie hoofdstuk 13). Categorieën die al in gebruik zijn maar
niet in de instellingenlijst staan — bijvoorbeeld uit een oudere Excel —
verschijnen automatisch mee in de keuzelijst, zodat een bewerking ze nooit
per ongeluk leegmaakt.

### Deelnemerslijst bewerken

Onder **Beheer > Deelnemerslijst bewerken** staat de volledige lijst met
een zoekveld erboven. Tik bij een station op **Bewerken** en je kan
roepnaam, naam, club, categorie, sectie en opmerking aanpassen. Zo hoef je
voor een tikfout of een laattijdige categoriewijziging niet meer de hele
Excel opnieuw te importeren.

Let op bij het wijzigen van een **roepnaam**: de roepnaam bepaalt welke
QSO's bij dit station horen. Corrigeer je een verkeerd gespelde roepnaam,
dan pikt de tracker meteen de QSO's op die tot dan toe genegeerd werden
omdat ze niet overeenkwamen met de lijst — de cellen kunnen dus ineens
groen worden. Manueel gezette statussen (overrides) verhuizen automatisch
mee naar de nieuwe roepnaam, zodat je die niet opnieuw moet zetten. Een
roepnaam die na normalisatie samenvalt met een station dat al in de lijst
staat, wordt geweigerd met een duidelijke melding.

Een station verwijderen kan ook vanuit dit paneel, met dezelfde knop en
dezelfde bevestiging als hieronder beschreven. Let wel: een station dat uit
de Excel komt en dat je hier aanpast, krijgt bij een **her-import van die
Excel** opnieuw de waarden uit het bestand. Pas dus ook het bronbestand aan
als de wijziging blijvend moet zijn.

**Een station verwijderen:** tik in de matrix op een cel van dat station en
kies onderaan het detailpaneel **Remove this station**. Er wordt eerst om
bevestiging gevraagd. Het station verdwijnt uit de lijst; reeds ontvangen
QSO's blijven op schijf bewaard, dus een her-import of het opnieuw
toevoegen van de roepnaam brengt alles terug. Zo raak je ook per ongeluk
toegevoegde of test-stations kwijt.

### Velddag exporteren en importeren (naar een andere pc)

In de sectie **Velddagen** van het Manage-paneel staat bij elke velddag een
**⭳-knop** (exporteren). Die schrijft de **volledige** velddag —
instellingen, deelnemers, álle QSO's en manuele statussen — naar één
`.fdtracker`-bestand. Kopieer dat bestand (USB, mail, netwerk) naar een
andere pc, en gebruik daar onderaan **"Import field day from file…"** om
verder te werken. Importeren maakt **altijd een nieuwe velddag** aan en
overschrijft dus nooit bestaande gegevens; je kan hetzelfde bestand ook
twee keer importeren zonder risico. Bij de importknop staat een blauw **(?)**
met deze uitleg.

> Zo kan je bijvoorbeeld op de veldpost werken, exporteren, en thuis of op
> een reservelaptop naadloos verdergaan met exact dezelfde stand.

### Velddag verwijderen (met beveiliging)

Naast elke **niet-actieve** velddag staat een **🗑-knop**. Omdat dit álle
onderliggende loggegevens definitief wist, vraagt het programma je eerst om
ter bevestiging het woord **DELETE** te typen. Typ je iets anders, dan
gebeurt er niets. Zo ruim je gerust testvelddagen op zonder gevaar voor je
echte data. Twee veiligheidsgrenzen: de **actieve** velddag kan niet
verwijderd worden (wissel eerst naar een andere), en er blijft **altijd
minstens één** velddag bestaan.

### Velddag afsluiten en heropenen

Manage → **Close field day** (met bevestiging): de velddag gaat op slot —
bekijken en exporteren kan nog, maar er komen geen QSO's meer binnen en
manuele wijzigingen en imports worden geweigerd. Bovenaan verschijnt een
oranje **CLOSED**-badge. **Reopen field day** (ook met bevestiging) maakt
alles weer actief, inclusief de UDP-ontvangst.

## 13. Instellingen

Open **Manage** en scrol naar **Settings**:

- **Taal** — Nederlands (standaard), Engels of Frans. De keuze werkt meteen
  door in de hele applicatie én op de publieke pagina, zodat bijvoorbeeld
  een Franstalige bezoeker de live-pagina in het Frans ziet.
- **UDP listen address** — `127.0.0.1` (veilig: enkel deze laptop) of
  `0.0.0.0` (ook andere N1MM-PC's op het netwerk mogen sturen). Poort
  standaard `12060`. Na opslaan herstart de ontvanger vanzelf op het
  nieuwe adres.
- **Stale after** — na hoeveel seconden stilte een bron-PC als STALE
  gemarkeerd wordt.
- **Strict callsign matching** — normaal UIT: `ON4BAF/P` en `ON4BAF` zijn
  hetzelfde station. Zet je dit aan, dan telt enkel de exacte roepnaam en
  wordt de matrix meteen herrekend.
- **Statuskleuren** — kies per status je eigen kleur; het ✎-symbool blijft
  altijd zichtbaar als niet-kleurgebonden markering.
- **Export folder** — waar CSV/PDF-exports terechtkomen (volgt).
- **Categorieën voor de keuzelijst** — één categorie per lijn. Dit is de
  lijst die je krijgt bij het toevoegen en bewerken van een station. Komt
  er een nieuwe UBA-categorie bij, dan voeg je hier gewoon een lijn toe;
  daar is geen nieuwe versie van het programma voor nodig. Lege lijnen en
  dubbels worden bij het opslaan automatisch weggehaald. Bestaande
  stations behouden altijd de categorie die ze al hadden, ook als je die
  uit de lijst haalt.

## 13b. Publiceren naar GitHub Pages

Hiermee kan iedereen — thuisblijvers, familie, andere secties — live
meevolgen op een gewone webpagina die zichzelf elke 30 seconden ververst.

> ⚠️ **De gepubliceerde pagina is openbaar.** Iedereen met de link ziet de
> roepnamen en de gewerkt-status. Opmerkingen en operatornotities worden
> **standaard weggelaten**; enkel als je het vinkje "Include remarks…"
> aanzet gaan ze mee.

### Eenmalige opzet (ook voor andere clubs die dit willen gebruiken)

**Stap 1 — GitHub-account en repo**
1. Maak (indien nodig) een gratis account op github.com.
2. Klik rechtsboven **+** → *New repository*. Naam bv. **`velddag-live`**.
   Zet op **Public**, vink *Add a README* aan, klik *Create repository*.

**Stap 2 — GitHub Pages aanzetten**
1. In die repo: **Settings → Pages**.
2. Bij *Source*: kies **Deploy from a branch**; branch **main**, map
   **/ (root)**; *Save*.
3. Na een minuutje staat bovenaan je publieke adres:
   `https://<jouwnaam>.github.io/velddag-live/`

**Stap 3 — Fine-grained token aanmaken (de "sleutel")**
1. GitHub: klik je profielfoto → **Settings** → helemaal onderaan
   **Developer settings** → **Personal access tokens** →
   **Fine-grained tokens** → *Generate new token*.
2. Naam: `velddag-tracker`. Vervaldatum: bv. 90 dagen.
3. **Repository access**: *Only select repositories* → kies enkel
   **velddag-live**.
4. **Permissions → Repository permissions → Contents: Read and write.**
   Verder niets.
5. *Generate token* en **kopieer hem meteen** (hij wordt maar één keer
   getoond).

**Stap 4 — In de tracker koppelen**
1. Manage → **Publish to GitHub Pages**.
2. Plak het token in het tokenveld en klik **Store token** — het wordt
   veilig in de wachtwoordkluis van je besturingssysteem bewaard (Windows
   Credential Manager), nooit in een bestand.
3. Vul *Repository* in (`jouwnaam/velddag-live`), branch `main`, map leeg.
4. Kies het interval (bv. elke 2 minuten) en vink *Automatic publishing*
   aan — of werk enkel met de knop **Publish now**.
5. Klik **Save publish settings**, dan **Publish now**. Popup meldt het
   resultaat; de link naar de publieke pagina staat eronder.

**Geen wachtwoordkluis (kale Linux-server)?** Zet dan de
omgevingsvariabele `N1MM_TRACKER_GH_TOKEN` met het token als waarde.

### Hoe het werkt

Bij elke publicatie gaan `snapshot.json` en de webpagina zelf naar de
repo; ongewijzigde bestanden worden overgeslagen. De publieke pagina is
exact dezelfde als je lokale, maar **alleen-lezen** — geen knoppen, geen
overrides. Netwerkfouten worden automatisch opnieuw geprobeerd en
blokkeren de tracker nooit.

Klik je op **Publish now** terwijl er al een publicatie loopt (bv. net op
het moment dat automatisch publiceren afgaat), dan krijg je de melding
"Er loopt al een publicatie — probeer het straks opnieuw" in plaats van een
foutmelding: de tweede poging wordt netjes geweigerd, niet uitgevoerd.

### Wat het publiek ziet, afhankelijk van de velddagstatus

De publieke pagina past zich automatisch aan:
- **Tijdens de velddag** (actieve velddag, binnen de periode): de live matrix.
- **Vóór de start**: een aankondiging "Field day starts soon" met de datum
  en een aftelling.
- **Geen actieve velddag** (alle afgesloten): "No active field day"; staat
  er al een volgende velddag gepland, dan toont hij naam en datum.
- **Vanaf één week na het einde**: de resultaten worden niet meer getoond
  ("This field day has ended"). Bij de niet-live toestanden staat er ook
  geen deelnemers- of QSO-data in het gepubliceerde bestand.

> Zorg dat *Automatic publishing* aan staat, zodat deze overgangen (bv. het
> verdwijnen na een week) vanzelf gepubliceerd worden.

> **Meerdere tracker-laptops** die via GitHub samenvloeien staat bewust
> **niet** in deze versie; het ontwerp staat klaar op de roadmap (zie
> README). Meerdere N1MM-PC's naar één tracker kan vandaag al gewoon.

## 14. Hoe werkt het technisch?

Voor wie onder de motorkap wil kijken: **`docs/ARCHITECTUUR.md`** bevat de
visuele architectuur (diagrammen die GitHub automatisch tekent), het
verloop van één QSO door het systeem, de bestandsindeling op schijf, de
statusbeslissing per cel, en de volledige lijst van API-endpoints. Kort:
één Python-proces met een UDP-luisterdraad en een webservertje; alle data
in gewone JSON-bestanden die atomisch geschreven worden; en één webpagina
die zowel lokaal als publiek dezelfde `snapshot.json` leest.

## 14b. Knoppen, help en de handleiding-knop

- Rechtsboven staan **Manual** (opent een korte handleiding in het scherm,
  met o.a. de N1MM- en **firewall**-instellingen) en **Manage** (het
  beheerpaneel). Op de gepubliceerde, publieke pagina zijn deze weg — die
  is enkel-lezen.
- **Windows Firewall**: de eerste keer dat je de tracker start, kan Windows
  vragen om netwerktoegang toe te staan. Klik **Toegang toestaan** — dat is
  nodig om de gegevens van N1MM te ontvangen. Weggeklikt? Sta dan
  `python.exe` toe via *Windows-beveiliging → Firewall- en
  netwerkbeveiliging → Een app toestaan*.
- In het Manage-paneel staan bij de technische velden kleine blauwe
  **(?)-cirkels**. Klik erop voor directe uitleg (N1MM-poort, strict
  matching, freshness, Excel-kolomkoppen, repository, token…).
- Het Manage-paneel is nu opgedeeld in **inklapbare secties** — klik een
  koptitel om ze open of dicht te klappen.

## 15. Wat als de app crasht tijdens de velddag?

Geen paniek — het systeem is hierop gebouwd:

- **Elk QSO wordt onmiddellijk en veilig op schijf bewaard** op het moment
  dat het binnenkomt (atomisch: er kan nooit een half bestand ontstaan,
  zelfs niet bij stroomuitval midden in een schrijfactie).
- **Herstarten** = het programma opnieuw starten (dubbelklik of
  `python -m app.main`). Gemeten hersteltijd: **minder dan een seconde**
  tot de pagina weer werkt; reken met browser erbij op enkele seconden.
- Na de herstart staat **alles** er terug: alle QSO's, manuele statussen,
  instellingen en de deelnemerslijst. QSO's die tijdens de uitval in N1MM
  gelogd werden, haal je binnen met een **ADIF-import** (hoofdstuk 11) —
  daar is die functie precies voor.
- Als allerlaatste vangnet staat elk ontvangen pakket ruw in
  `raw_packets.log` in de velddagmap.

**Was de tracker een tijd uit terwijl in N1MM werd doorgelogd?** UDP draagt
enkel live-verkeer, dus die QSO's zijn niet vanzelf ontvangen. Haal ze in
één keer binnen: in N1MM **File → Export → Export to ADIF**, en in de
tracker **Manage → ADIF import**. Reeds bekende QSO's worden overgeslagen,
dus je kan dit zo vaak doen als je wil zonder dubbels. Bij de ADIF-knop
staat een blauw **(?)** met deze uitleg.

Test dit gerust zelf vooraf: testplan **A6**.

## 15b. Installeren als programma — voor gewone gebruikers

> **Alles staat op één pagina:**
> <https://on3vz.github.io/n1mm-fieldday-tracker/> — daar download je altijd
> de laatste versie (Windows en Linux) en staat dezelfde uitleg als hier,
> plus de versiegeschiedenis.

Vanaf deze versie is er een **installer**: één bestand
(`N1MMFieldDayTracker-Setup-x.y.z.exe`) dat je clubleden dubbelklikken.
Er is **geen Python, geen venv en geen enkel commando** nodig — de
Python-runtime zit mee in het programma.

### Installeren

1. Dubbelklik de setup. Windows vraagt om **beheerrechten** — klik Ja.
   (Dat is nodig voor de installatiemap en de firewall-regel.)
2. De installer vraagt onderweg om de **standaardinstellingen**:
   UDP-luisteradres (`127.0.0.1`), UDP-poort (`12060`) en de taal (`nl`).
   Aanvaard ze gewoon als N1MM op dezelfde laptop draait.
3. De installer zet een **snelkoppeling op het bureaublad** en in het
   startmenu, en voegt automatisch de **Windows Firewall-regel** toe zodat
   de N1MM-pakketten binnenkomen.
4. Op het einde verschijnt een herinnering met de **N1MM-instructie**
   (Config → Broadcast Data → Contacts → adres:poort). Niet vergeten!

> De ingevulde standaardwaarden worden enkel weggeschreven als er nog geen
> instellingen bestaan. Herinstalleer je later, dan blijven jouw eigen
> instellingen dus gewoon staan.

### Starten en afsluiten

Dubbelklik de snelkoppeling. Er opent een klein zwart venster (de server) en
je browser gaat vanzelf naar de tracker. **Afsluiten** doe je met
**Beheer → Applicatie → Applicatie afsluiten**, of door het zwarte venster te
sluiten. De server stopt dan netjes mee.

### Ontvangst na slaapstand

Ging de laptop in slaapstand, dan kan de UDP-ontvangst stilvallen. De app
**herstelt dat nu automatisch**: een bewaker controleert elke tien seconden of
de ontvanger nog leeft en herstart hem indien nodig. Merk je toch iets, dan is
er de knop **Beheer → Applicatie → Ontvangst herstarten** (met (?)-uitleg),
die de luisteraar opnieuw opent zonder de app te herstarten.

### Updaten

Ga naar **Beheer → Applicatie**. Daar staat je huidige **versienummer** en de
knop **Controleer op updates**. Is er een nieuwe versie, dan zie je welke, en
met **Nu downloaden en installeren** haalt de app de nieuwe setup op en start
die. Bevestig de Windows-melding en de nieuwe versie wordt over de oude
geïnstalleerd.

> **Je velddaggegevens blijven altijd staan.** Die staan in
> `%LOCALAPPDATA%\N1MM Field Day Tracker\`, buiten de programmamap — een
> update of herinstallatie raakt ze niet.

Geen internet? Dan meldt de controle netjes dat GitHub niet bereikbaar was;
er gebeurt verder niets.

### Verwijderen (uninstall)

Via **Instellingen → Apps → N1MM Field Day Tracker → Verwijderen**. De
verwijderaar haalt ook de firewall-regel weg en **vraagt** of je de
velddaggegevens wil wissen — standaard **nee**, zodat je niet per ongeluk je
logs kwijtraakt.

### Linux

Download het `.tar.gz`-pakket van de downloadpagina en draai:

```
tar xzf N1MMFieldDayTracker-*-linux-x86_64.tar.gz
cd N1MMFieldDayTracker-*-linux-x86_64
./install.sh
```

Geen root nodig — alles komt in je eigen home-map. Daarna staat het programma
in je menu, of start je het met `n1mm-fieldday-tracker`. Verwijderen kan met
`./install.sh --uninstall`; je velddaggegevens blijven dan staan.

Draait N1MM op een andere pc en gebruik je `ufw`? Sta de poort toe met
`sudo ufw allow 12060/udp`.

### Zelf de installer bouwen (voor de beheerder)

Dat gebeurt **automatisch**. Verhoog het versienummer in `app\version.py`,
push een tag `vX.Y.Z`, en GitHub bouwt zelf de Windows-installer én het
Linux-pakket en publiceert de Release. De downloadpagina en de updateknop in
de app pikken dat vanzelf op. Het volledige stappenplan staat in
`RELEASE.md`.

Moet het toch lokaal (bv. GitHub ligt plat), dan kan je op een Windows-pc
`packaging\build.bat` dubbelklikken; dat vereist eenmalig Python en
Inno Setup 6 — zie `packaging\README-BUILD.md`.

## 16. Problemen oplossen

### `python` wordt niet herkend (Windows)

Python staat niet in je PATH. Herinstalleer Python en vink **"Add python.exe
to PATH"** aan, of gebruik `py -m app.main` in plaats van
`python -m app.main`.

### `No module named app`

Je staat niet in de juiste map. Doe eerst `cd` naar de map
`n1mm_fieldday_tracker` (de map waarin `app\` en `README.md` staan) en
probeer opnieuw.

### `(.venv)` staat niet vooraan mijn prompt

De virtuele omgeving is niet actief. Voer eerst
`.venv\Scripts\activate` (Windows) of `source .venv/bin/activate` (Linux)
uit.

### N1MM-QSO's komen niet binnen

Overloop in deze volgorde:

1. **Checkbox**: staat *Contacts* aangevinkt in Broadcast Data? (hfdst. 7)
2. **Adres**: staat er exact `127.0.0.1:12060`? (bij een aparte N1MM-PC:
   het IP van de trackerlaptop, en in de tracker-settings host `0.0.0.0`)
3. **Firewall**: laat Windows Firewall inkomend UDP-verkeer op poort 12060
   toe voor de tracker? Bij de eerste start vraagt Windows dit meestal —
   klik dan op *Toegang toestaan*.
4. **Poortconflict**: gebruikt een andere N1MM-plugin of programma al poort
   12060? De tracker meldt dit bij het opstarten ("cannot bind").
5. **Diagnose per bron-PC**: de tracker toont per PC het laatste
   ontvangstmoment — zo zie je meteen wélke computer niet doorstuurt.
6. **Test**: log een test-QSO in N1MM en verwijder het meteen weer; er
   moeten dan pakketten binnenkomen.

*(dit hoofdstuk groeit verder mee met elke fase)*

---

*Handleiding bijgewerkt bij: fase 19 (downloadpagina met handleiding,
Linux-installatie, en geautomatiseerd releasebeheer via GitHub Actions).*
