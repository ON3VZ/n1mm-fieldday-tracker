# De installer bouwen (voor de beheerder)

Je hebt dit maar nodig als je een **verspreidbare setup.exe** wil maken voor
clubleden. Om de tracker zelf te draaien heb je dit niet nodig.

## Eenmalig installeren op de bouw-pc
1. **Python 3.11+** van https://www.python.org/downloads/ — vink bij het
   installeren **"Add python.exe to PATH"** aan.
2. **Inno Setup 6** van https://jrsoftware.org/isdl.php (gewoon Next-Next).

## Bouwen
Dubbelklik **`packaging\build.bat`**. Het script:
- maakt een aparte bouw-omgeving (raakt je gewone installatie niet),
- installeert PyInstaller en de app-pakketten,
- bouwt de `.exe`,
- bouwt de installer.

Klaar? De installer staat in **`packaging\Output\`** als
`N1MMFieldDayTracker-Setup-<versie>.exe`. Dat ene bestand deel je met je
clubleden — zij dubbelklikken en installeren, zonder Python of commando's.

## Een nieuwe versie uitbrengen (voor de auto-update)
1. Verhoog het versienummer in **`app\version.py`** (bv. `1.0.0` → `1.1.0`).
2. Bouw opnieuw met `build.bat`.
3. Maak op GitHub een **Release** met tag `v1.1.0` en hang de nieuwe
   `N1MMFieldDayTracker-Setup-1.1.0.exe` eraan als bijlage (asset).
4. Klaar. Gebruikers zien via **Beheer > Applicatie > Controleer op updates**
   dat er een nieuwe versie is, en installeren ze met één klik.
