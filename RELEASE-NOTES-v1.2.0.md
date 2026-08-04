# v1.2.0 — sectiekolom, instelbare categorieregel en vaste lijstindeling

## Nieuw

**Sectie in de matrix.** Naast de roepnaam staat nu een smalle kolom met de
UBA-sectie van het station. De kolom blijft mee vastgeplakt bij horizontaal
scrollen, net als de roepnaamkolom, en verschijnt alleen wanneer er secties
in de deelnemerslijst staan. Filteren op sectie werkt zoals voorheen.

**Categorieregel aan of uit.** In *Instellingen* staat een nieuw vinkje
"Categorie onder de callsign tonen". Zet je het uit, dan verdwijnt de
lichtgrijze regel onder elke roepnaam en wordt de matrix een pak compacter —
handig wanneer je veel banden tegelijk op het scherm wil. De keuze reist mee
naar de gepubliceerde pagina, zodat die er identiek uitziet. Filteren op
categorie blijft in beide standen werken.

## Gewijzigd

**Vaste indeling voor de deelnemerslijst.** De lijst moet vanaf nu deze
kolomkoppen bevatten: `Call`, `categorie`, `sectie` en minstens één
bandkolom (`40M`, `80M`, `160M`, …). Ontbreekt er één, dan wordt het bestand
in zijn geheel geweigerd — er wordt niets half geïmporteerd en je bestaande
lijst blijft ongewijzigd. Op het scherm verschijnt een kader met de
ontbrekende kolommen, de koppen die wél in je bestand stonden, en de
volledige vereiste indeling met voorbeeldwaarden.

De volgorde van de kolommen blijft vrij, synoniemen (`Callsign`, `Roepnaam`,
`Category`, `Section`) blijven aanvaard en extra kolommen zoals `Nummer`
worden nog steeds genegeerd. Bestaande deelnemerslijsten blijven dus gewoon
werken. Dezelfde controle geldt voor CSV-bestanden.

## Bijgewerkt

- Handleiding: nieuwe paragraaf over het vaste formaat en wat te doen bij
  een geweigerd bestand.
- Vertalingen aangevuld in het Nederlands, Engels en Frans.

## Upgraden

Windows: download de installer hieronder en voer ze uit over je bestaande
installatie, of gebruik in de app *Beheer → Controleren op updates*.
Linux: download het pakket hieronder en draai `install.sh` opnieuw.

Je velddagen, stations, QSO's en manuele statussen blijven behouden.
