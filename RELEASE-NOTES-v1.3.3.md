# v1.3.3 — geen race meer op snapshot.json bij publiceren

Datum: 17 augustus 2026
Repo: https://github.com/ON3VZ/n1mm-fieldday-tracker

Naar aanleiding van de `HTTP 409 "snapshot.json does not match <sha>"`-
fouten die optraden bij het publiceren. Aan de engine, N1MM-ontvangst,
opslag en het datamodel is niets gewijzigd.

## Het probleem

Elke publicatie haalt per bestand eerst de huidige sha op GitHub op, en
gebruikt die om te bewijzen "ik overschrijf de laatst gekende versie".
**Automatisch publiceren** (een achtergrondthread) en de knop **Publish
now** (een aparte thread per klik) konden ongemerkt gelijktijdig lopen —
er was geen enkele onderlinge afstemming tussen beide. Liepen twee
publicaties zo goed als tegelijk, dan kon de tweede z'n PUT met een
ondertussen verouderde sha indienen, wat GitHub afwijst met HTTP 409.

Enkel `snapshot.json` werd hierdoor geraakt: dat bestand bevat een
tijdstempel en live data, en is dus **bij elke publicatie anders**.
`index.html`, `app.js` en `style.css` zijn bij twee gelijktijdige runs
byte-identiek, dus zodra de ene ze wegschrijft, ziet de andere bij zijn
eigen sha-check gewoon "inhoud al gelijk" en slaat hij ze over — geen
conflict mogelijk. Vandaar dat alleen `snapshot.json` in de foutmeldingen
opdook, herhaaldelijk, terwijl de rest van de publicatie wél lukte.

## Wat er gewijzigd is

**1. Eén publicatie tegelijk.** `AppState` heeft een eigen
`threading.Lock` gekregen die specifiek `publish_now()` bewaakt (los van
de bestaande lock die de motorstatus beschermt). De lock is
niet-blokkerend: een tweede aanroep terwijl er al een publicatie loopt,
wordt onmiddellijk geweigerd met `{"ok": false, "already_running": true}`
— zonder ook maar één GitHub-aanvraag te doen — in plaats van te racen.
De knop toont dan "Er loopt al een publicatie — probeer het straks
opnieuw" (nl/en/fr).

**2. Automatisch herstel bij een 409.** Mocht het conflict tóch optreden
— bv. door een tweede laptop of proces die buiten deze lock publiceert,
wat expliciet niet ondersteund is in deze versie, maar niet mag leiden
tot een harde fout — dan haalt `GitHubPublisher.publish_file()` bij een
409 de actuele sha opnieuw op en probeert die ene upload tot
`CONFLICT_RETRIES` (3) keer opnieuw, met een korte pauze ertussen. Pas als
alle pogingen mislukken, wordt het als fout gerapporteerd.

## Gewijzigde bestanden (5)

```
app/version.py                  1.3.2 → 1.3.3
app/server.py                   AppState._publish_lock; publish_now()
                                 opgesplitst in de lock-wrapper en
                                 _publish_now_locked() met de bestaande inhoud
app/publish/github_publisher.py CONFLICT_RETRIES/CONFLICT_BACKOFF_SECONDS;
                                 publish_file() herhaalt bij een 409
app/view/static/app.js          api(): herkent already_running net als
                                 offline; "pub.busy"-melding (nl/en/fr)
docs/HANDLEIDING.md             §13b: korte alinea over de nieuwe melding
tests/test_publish.py           + 4 tests (2 op de publisher, 2 op AppState)
```

## Self-check (§11.2)

**Geverifieerd** — volledige testsuite **407 tests groen** (4 nieuw).
`node --check` op `app.js` zonder fouten.

**Wat werkt** —
- Een 409 op één bestand herstelt zichzelf zonder de rest van de
  publicatie te laten mislukken (`test_conflict_retries_with_a_fresh_sha`).
- Blijft het conflict aanhouden, dan geeft de publisher na 3 pogingen een
  duidelijke fout terug in plaats van oneindig te blijven proberen
  (`test_conflict_exhausts_retries_then_reports_the_error`).
- Een publicatie die start terwijl de lock al vast zit, doet **geen enkele**
  netwerkaanroep en meldt zich netjes af
  (`test_overlapping_publish_is_turned_away_not_raced`).
- Na afloop is de lock weer vrij voor de volgende run
  (`test_publish_still_works_once_the_lock_is_free`).

**Wat open blijft** — een échte twee-threads-race is bewust niet als test
opgenomen (de uitkomst hangt af van threadplanning en zou de testsuite
onbetrouwbaar maken); de dekking zit op het niveau van "wat moet er
gebeuren als de lock al bezet is" en "wat moet er gebeuren bij een 409",
wat samen het volledige gedrag vastlegt.

**Risico's en aannames** — de lock beschermt enkel tegen gelijktijdige
publicaties **binnen dezelfde draaiende tracker**. Twee laptops die
onafhankelijk van elkaar naar dezelfde repo publiceren (nadrukkelijk niet
ondersteund, zie roadmap) vallen buiten deze lock; de 409-retry in
`github_publisher.py` vangt dat scenario op best-effort basis mee op,
maar is er niet specifiek voor ontworpen.
