# v1.3.0 — categorielijst, deelnemerslijst bewerken, versie in de banner

## Nieuw

**Categorie kies je uit een lijst.** Bij het toevoegen én het bewerken van
een station is de categorie geen vrij tekstveld meer maar een keuzelijst.
Een tikfout maakte tot nu toe stilzwijgend een tweede categorie aan,
waardoor de statistiek per categorie in twee splitste en het filter twee
bijna identieke regels toonde. De lijst wordt gevuld met de UBA-categorieën
(Restricted A12u, Restricted A24u, Open All Bands B.LP, Open All Bands
A.HP, QRP C12u, QRP C24u, Fixed 24u, SWL 24u).

Staat de gewenste categorie er niet bij, dan blijft **Andere… (zelf
intypen)** beschikbaar. Categorieën die al in gebruik zijn maar niet in de
lijst staan — bijvoorbeeld uit een oudere Excel — verschijnen automatisch
mee in de keuzelijst, zodat een bewerking ze nooit per ongeluk leegmaakt.

**De categorielijst is een instelling, geen vaste lijst in de code.** Onder
*Instellingen* staat een tekstvak met één categorie per lijn. Komt er een
nieuwe UBA-categorie bij, dan voeg je gewoon een lijn toe — daar is geen
nieuwe versie van het programma voor nodig. Lege lijnen en dubbels worden
bij het opslaan automatisch weggehaald.

**Deelnemerslijst handmatig bewerken.** Nieuw paneel *Beheer >
Deelnemerslijst bewerken*: de volledige lijst met een zoekveld erboven, en
per station een knop **Bewerken** waarmee je roepnaam, naam, club,
categorie, sectie en opmerking aanpast. Voor een tikfout of een laattijdige
categoriewijziging moet je dus niet langer de hele Excel opnieuw
importeren.

Het wijzigen van een roepnaam is daarbij niet zomaar een tekstwijziging:
de roepnaam bepaalt welke QSO's bij een station horen. Corrigeer je een
verkeerd gespelde roepnaam, dan pikt de tracker meteen de QSO's op die tot
dan toe genegeerd werden omdat ze niet in de deelnemerslijst voorkwamen —
cellen kunnen dus ineens groen worden. Manueel gezette statussen verhuizen
automatisch mee naar de nieuwe roepnaam, zodat je die niet opnieuw moet
zetten. Een roepnaam die na normalisatie samenvalt met een station dat al
in de lijst staat, wordt geweigerd met een duidelijke melding.

**Versienummer in de banner.** Bovenaan staat nu `v1.3.0` naast de periode.
Het nummer reist mee in `snapshot.json`, dus ook de gepubliceerde pagina
toont de versie die ze gemaakt heeft. Bij een probleemmelding is meteen
duidelijk over welke versie het gaat, zonder eerst het beheerpaneel te
moeten opendoen.

## Gewijzigd

**"Matrix" heet nu "Tabel".** Het eerste tabblad heette Matrix; dat is
vakjargon dat niet iedereen in de club vlot leest. Het heet nu **Tabel**
(Engels: Table, Frans: Tableau). Enkel het label wijzigt — de weergave,
de filters en de interne benamingen blijven ongewijzigd.

## Technisch

- Nieuwe eindpunten `GET /api/stations` en `POST /api/station/update`.
- `snapshot.json` bevat een nieuw veld `app_version`.
- `app_settings.json` bevat een nieuw veld `station_categories`. Een
  settingsbestand van vóór deze versie krijgt automatisch de
  standaardlijst; een bewust leeggemaakte lijst blijft leeg.
- 19 nieuwe tests; de volledige suite telt er 401 en is groen.
