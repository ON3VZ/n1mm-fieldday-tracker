# N1MM Field Day Tracker — Architectuur en technische werking

> Diagrammen in dit document zijn **Mermaid**: GitHub toont ze automatisch
> als echte tekeningen. Onder elk diagram staat een ASCII-versie voor wie
> offline leest. Bijgewerkt bij: fase 12.

---

## 1. Overzicht in één beeld

```mermaid
flowchart LR
    subgraph N1MM["N1MM Logger+ (1..n PC's)"]
        PC1[PC 1]
        PC2[PC 2]
        PC3[PC 3]
    end

    subgraph Tracker["N1MM Field Day Tracker (Python, één proces)"]
        LIS["ingest/n1mm_listener<br/>UDP :12060, eigen thread"]
        PAR["ingest/n1mm_parser<br/>roottag-filter, veldmapping"]
        ADIF["ingest/adif_importer<br/>vangnet + dedup"]
        EXC["ingest/station_importer<br/>Excel/CSV"]
        ENG["core/sync_engine<br/>matrix = f(velddag, stations,<br/>QSO's, overrides)"]
        MAT["core/matching + callsign + band_plan"]
        REPO["storage/fieldday_repository<br/>atomic JSON per velddag"]
        SNAP["view/snapshot_builder<br/>snapshot.json"]
        SRV["server.py<br/>HTTP :8765 + JSON-API"]
    end

    subgraph Clients["Weergave (één implementatie)"]
        LOCAL["Browser lokaal<br/>(bewerken kan)"]
        PUB["GitHub Pages<br/>(alleen-lezen)"]
    end

    PC1 & PC2 & PC3 -- "UDP contactinfo/<br/>replace/delete" --> LIS
    LIS --> PAR --> ENG
    ADIF --> ENG
    EXC --> REPO
    ENG <--> MAT
    ENG <--> REPO
    ENG --> SNAP --> SRV
    SRV <--> LOCAL
    SNAP -. "publish (fase 16)" .-> PUB
```

ASCII-fallback:

```
N1MM PC's ──UDP:12060──▶ listener ─▶ parser ─▶ sync engine ◀─▶ matching
ADIF-bestand ───────────────────────────────▶     │              band_plan
Excel/CSV ──▶ station_importer ──▶ repository ◀───┘              callsign
                                       │
                              snapshot_builder ─▶ snapshot.json
                                       │                │
                              server.py :8765    GitHub Pages (later)
                                       │
                              browser (lokaal, bewerkt)
```

**Kernbeslissing (§3.1 van de spec):** de webview bestaat één keer, als
statische HTML/JS die `snapshot.json` leest. Lokaal serveert de app die
view; bij publicatie gaat exact dezelfde snapshot + view naar GitHub
Pages. Er bestaat dus géén tweede implementatie van matrix-, filter- of
kleurenlogica.

## 2. Wat gebeurt er bij één gelogd QSO?

```mermaid
sequenceDiagram
    participant N as N1MM
    participant L as UDP-listener (thread)
    participant P as Parser
    participant E as SyncEngine
    participant R as Repository (schijf)
    participant B as Browser

    N->>L: contactinfo (XML, UDP)
    L->>L: raw → raw_packets.log
    L->>P: parse_packet()
    P-->>L: QSO (band uit rxfreq, BR-08)
    L->>E: upsert_qso(QSO)
    E->>E: match (callsign+band, BR-04)<br/>cel herrekenen, override wint (BR-05)
    E->>R: received_qsos.json (atomisch)
    Note over B: browser pollt elke 5 s
    B->>+E: GET /snapshot.json
    E-->>-B: verse snapshot → cel kleurt groen
```

Bij **bewerken** in N1MM komt eerst `contactdelete`, dan `contactreplace`
(zelfde ID): de engine herrekent oude én nieuwe cel. Bij **verwijderen**
wordt het QSO-record gemarkeerd `deleted=true` maar nooit gewist — de
geschiedenis blijft reconstrueerbaar.

## 3. Gegevens op schijf

```mermaid
flowchart TB
    ROOT["<appdata>/N1MM Field Day Tracker/"]
    SET["app_settings.json<br/>taal, UDP, laatste velddag"]
    FDS["fielddays/"]
    FD1["&lt;velddag-slug&gt;/"]
    A["fieldday.json — periode, banden, instellingen"]
    B2["stations.json — deelnemerslijst"]
    C["received_qsos.json — alle QSO's, ook deleted"]
    D["overrides.json — manuele statussen"]
    E2["sync_log.json — import-/syncrapporten"]
    F["raw_packets.log — elk ruw UDP-pakket"]
    G["exports/ — CSV/PDF (fase 15)"]
    ROOT --> SET
    ROOT --> FDS --> FD1
    FD1 --> A & B2 & C & D & E2 & F & G
```

- `<appdata>` = `%LOCALAPPDATA%` (Windows) of `~/.local/share` (Linux)
- **Elke schrijfactie is atomisch**: eerst `.tmp`, teruglezen en parsen ter
  controle, dan pas vervangen. Een stroomuitval halverwege kan dus nooit
  een half bestand achterlaten.
- Een **corrupt** bestand wordt niet gewist maar opzijgezet als
  `<naam>.corrupt.<tijdstip>` — inspecteerbaar achteraf; de app start
  gewoon verder met een lege structuur.

## 4. De statusbeslissing per cel

```mermaid
flowchart TD
    Q["QSO"] --> D1{deleted?}
    D1 -- ja --> X[telt niet]
    D1 -- nee --> D2{X-QSO?<br/>IsClaimedQso=0}
    D2 -- ja --> X
    D2 -- nee --> D3{callsign in<br/>deelnemerslijst?}
    D3 -- nee --> X2["genegeerd (BR-03)<br/>wel ruw bewaard"]
    D3 -- ja --> D4{binnen<br/>velddagperiode?}
    D4 -- nee --> X
    D4 -- ja --> D5{band geselecteerd?}
    D5 -- nee --> X
    D5 -- ja --> W["cel: gewerkt via N1MM"]
    W --> OV{override op<br/>callsign+band?}
    OV -- nee --> GROEN["WORKED_BY_N1MM"]
    OV -- ja --> MAN["override wint altijd (BR-05):<br/>EXCLUDED &gt; MANUAL_NOT_WORKED &gt;<br/>MANUAL_WORKED"]
```

Normalisatie (`ON4BAF/P` ≡ `ON4BAF` ≡ `F/ON4BAF/P` in losse modus) wordt
bij het matchen toegepast op **beide** kanten, telkens opnieuw vanaf de
originele roepnamen — daarom werkt de strict/loose-schakelaar ook met
terugwerkende kracht na een hersync.

## 5. Draden en processen

Eén Python-proces met drie draden:

| Draad | Doet | Mag nooit |
|---|---|---|
| UDP-listener | pakketten ontvangen, parsen, engine voeden, persisteren | stoppen door één slecht pakket |
| HTTP-server (threadpool) | view + snapshot + API serveren | businesslogica bevatten (BR-13) |
| Hoofddraad | opstart, shutdown (Ctrl+C) | — |

Engine-toegang is beveiligd met één lock in `AppState`; de engine zelf is
puur (geen I/O) en daardoor volledig testbaar zonder N1MM en zonder UI.

## 6. JSON-API (lokaal, poort 8765)

| Methode + pad | Doel |
|---|---|
| `GET /snapshot.json` | Verse snapshot; de view pollt dit elke 5 s (30 s publiek) |
| `GET /api/status` | Listenertellers + freshness per bron-PC |
| `POST /api/override` | Manuele status zetten (`manual_worked` / `manual_not_worked` / `excluded`) |
| `POST /api/override/clear` | Override wissen → automatische status geldt weer |
| `POST /api/sync` | Volledige herberekening + rapport naar sync-log |
| `POST /api/station-remarks` | Opmerking bij een station bewerken |
| `GET /api/fielddays` | Alle velddagen |
| `POST /api/fieldday/create` | Nieuwe velddag (optioneel gekopieerd van bestaande) |
| `POST /api/fieldday/activate` | Wisselen van actieve velddag |
| `POST /api/fieldday/update` | Actieve velddag bewerken (naam, periode, banden, …) |
| `POST /api/import-stations` | Deelnemerslijst uploaden (xlsx/csv, base64) met §7.3-bevestigingsflow |
| `POST /api/import-adif` | ADIF-bestand uploaden; retourneert het importrapport |

## 7. Testpiramide

```
        ┌───────────────────────────────┐
        │ docs/TESTPLAN.md (handmatig,  │  generale repetitie met N1MM
        │ delen A–G)                    │
        ├───────────────────────────────┤
        │ tests/test_server.py          │  echte UDP + echte HTTP, hele keten
        ├───────────────────────────────┤
        │ integratie: parser→engine,    │
        │ ADIF→engine, importer→repo    │
        ├───────────────────────────────┤
        │ unit: callsign, band_plan,    │  incl. de §9.2-regressietest:
        │ matching, sync_engine, store, │  incrementeel ≡ volledige hersync
        │ parsers, snapshot             │
        └───────────────────────────────┘
```

Draaien: `python -m pytest tests/` — alles moet altijd groen zijn.
