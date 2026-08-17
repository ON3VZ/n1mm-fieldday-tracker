# v1.3.1 — leesbare tabel op een smartphone

Datum: 17 augustus 2026
Repo: https://github.com/ON3VZ/n1mm-fieldday-tracker

Een correctierelease, enkel voor de webweergave. Aan de engine, de
N1MM-ontvangst, de opslag en het datamodel is niets gewijzigd.

## Het probleem

Op een smartphone waren de bovenste stations van de tabel niet leesbaar:
ze zaten verstopt onder de kolomkoppen, terwijl het filterpaneel bovenaan
gewoon zichtbaar bleef staan. Op pc en tablet deed het probleem zich niet
voor.

Oorzaak was **geen** overlappend filterpaneel, maar een dubbele scroll. De
tabel zit in een eigen scrollvenster met

```css
.matrix-wrap { overflow: auto; max-height: calc(100vh - 240px); }
```

Die 240 px is een vaste aanname voor de hoogte van topbalk + tabbladen +
filters. Op een pc klopt dat ongeveer. Op een smartphone wikkelen de
tabbladen over twee rijen en de filters over drie, samen met de topbalk al
gauw 400 à 450 px. Het scrollvenster was daardoor hoger dan de ruimte die
er nog was: het liep onderaan door achter de vaste legende, en een veeg
scrollde *binnen de tabel* in plaats van de pagina. De bovenste rijen
schoven zo onder de sticky kolomkoppen, zonder dat de gebruiker doorhad
dat hij aan het scrollen was.

## Wat er gewijzigd is

1. **Hoogte van de tabel wordt gemeten in plaats van geraden.** Op schermen
   smaller dan 700 px berekent `fitMatrixHeight()` in `app.js` de resterende
   hoogte uit de werkelijke positie van de tabel, de schermhoogte en de
   gemeten hoogte van de legende, en zet die in de CSS-variabele
   `--matrix-max-h`. Herberekend bij elke render, bij resize en bij het
   draaien van het toestel. Op pc en tablet wordt de variabele niet gezet en
   blijft de bestaande `calc(100vh - 240px)` gelden — daar verandert dus
   niets.
2. **Filterpaneel klapt dicht op een smartphone**, achter de knop
   *Filters ▾* (standaard dicht). Dat wint ongeveer 150 px, goed voor drie
   tot vier extra stationsrijen. Is er een filter actief, dan verschijnt er
   een blauw bolletje op de knop, zodat een half lege tabel niet als
   ontbrekende data gelezen wordt.
3. **Tabbladen op één horizontaal schuifbare rij** in plaats van twee
   gewikkelde rijen.
4. **Compactere legende** op een smartphone, en de andere weergaven houden
   nu onderaan exact de gemeten legendehoogte vrij (`--legend-h`) in plaats
   van een vaste 2,5 rem, zodat de laatste regels er niet meer achter
   verdwijnen.
5. **Cache-busting bij publicatie.** De gepubliceerde `index.html` verwijst
   voortaan naar `style.css?v=1.3.1` en `app.js?v=1.3.1`. Zonder dat kan een
   telefoon na een update nog dagenlang de oude stylesheet uit de cache
   serveren en zou deze correctie onzichtbaar blijven. Enkel de gepubliceerde
   kopie wordt herschreven; de lokale bestanden blijven ongewijzigd.

## Gewijzigde bestanden (7)

```
app/version.py                  1.3.0 → 1.3.1
app/server.py                   _version_asset_links() + toepassing in publish_now
app/view/static/index.html      knop Filters ▾ boven het filterpaneel
app/view/static/app.js          fitMatrixHeight, setFiltersCollapsed, i18n filter.toggle
app/view/static/style.css       @media (max-width: 700px) uitgebreid
docs/HANDLEIDING.md             hoofdstuk 10: paragraaf over de smartphoneweergave
tests/test_publish.py           + 2 tests en extra asserts op index.html
```

## Self-check (§11.2)

**Geverifieerd** — volledige testsuite **403 tests groen** (2 nieuw);
`node --check` op `app.js` zonder fouten.

**Wat werkt** — de synclogica, manual overrides (BR-05), het negeren van
onbekende calls (BR-03), UTC-behandeling (BR-06), band uit frequentie
(BR-08) en het filteren van `lookupinfo` (§5.3) zijn niet aangeraakt: deze
release wijzigt geen enkele regel in `core/`, `ingest/` of `storage/`.

**Wat open blijft** — de nieuwe layout is statisch geverifieerd, niet op een
echt toestel. Test op de telefoon: bij het openen moet het eerste station
(ON4BAF/p) zichtbaar zijn zonder te scrollen, moet de tabel onderaan net
boven de legende eindigen, en moet een veeg over de tabel de rijen scrollen
zonder dat de bovenste rij onbereikbaar wordt.

**Risico's en aannames** — de gemeten hoogte gaat uit van een niet-gescrolde
pagina; scrol je de topbalk weg, dan blijft er onderaan wat witruimte over.
Dat is bewust: het alternatief (herberekenen tijdens het scrollen) geeft een
springende tabel. Op een smartphone zit de knop *Station toevoegen* nu in
het dichtgeklapte filterpaneel — dat panel moet je eerst openvouwen.

## Uitrollen

De publicatiecode stuurt bij elke publicatie niet alleen `snapshot.json`
mee, maar ook `index.html`, `app.js` en `style.css`. Op de publicerende pc
volstaat het dus om v1.3.1 te installeren en één keer te publiceren; de
GitHub Pages-kopie wordt daarbij overschreven. Handmatige aanpassingen in
die repo gaan bij een volgende publicatie verloren — de repo is een
publicatiedoel, geen bron.
