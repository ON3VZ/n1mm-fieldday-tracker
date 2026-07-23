#!/usr/bin/env bash
# N1MM Field Day Tracker — installatie op Linux
#
# Gebruik:  ./install.sh            (installeren voor de huidige gebruiker)
#           ./install.sh --uninstall (verwijderen)
#
# Er is geen root nodig: alles komt in je eigen home-map te staan.

set -euo pipefail

APP_NAME="N1MM Field Day Tracker"
INSTALL_DIR="${HOME}/.local/share/n1mm-fieldday-tracker"
BIN_LINK="${HOME}/.local/bin/n1mm-fieldday-tracker"
DESKTOP_FILE="${HOME}/.local/share/applications/n1mm-fieldday-tracker.desktop"
DATA_DIR="${XDG_DATA_HOME:-${HOME}/.local/share}/n1mm-fieldday-tracker-data"

uninstall() {
  echo "== ${APP_NAME} verwijderen =="
  rm -rf "${INSTALL_DIR}"
  rm -f "${BIN_LINK}" "${DESKTOP_FILE}"
  command -v update-desktop-database >/dev/null 2>&1 &&
    update-desktop-database "${HOME}/.local/share/applications" 2>/dev/null || true
  echo "Programma verwijderd."
  echo
  echo "Je velddaggegevens staan NOG in:"
  echo "  ${HOME}/.local/share/N1MM Field Day Tracker/"
  echo "Verwijder die map handmatig als je ook alle logs wil wissen."
  exit 0
}

[[ "${1:-}" == "--uninstall" ]] && uninstall

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "== ${APP_NAME} installeren =="

if [[ ! -f "${SCRIPT_DIR}/N1MMFieldDayTracker" ]]; then
  echo "FOUT: N1MMFieldDayTracker niet gevonden naast dit script." >&2
  echo "Pak eerst het .tar.gz-pakket volledig uit en draai install.sh daarbinnen." >&2
  exit 1
fi

echo "[1/4] Bestanden kopiëren naar ${INSTALL_DIR}"
mkdir -p "${INSTALL_DIR}"
cp -r "${SCRIPT_DIR}/." "${INSTALL_DIR}/"
chmod +x "${INSTALL_DIR}/N1MMFieldDayTracker"

echo "[2/4] Startcommando aanmaken (${BIN_LINK})"
mkdir -p "$(dirname "${BIN_LINK}")"
ln -sf "${INSTALL_DIR}/N1MMFieldDayTracker" "${BIN_LINK}"

echo "[3/4] Menu-item aanmaken"
mkdir -p "$(dirname "${DESKTOP_FILE}")"
sed "s|@EXEC@|${INSTALL_DIR}/N1MMFieldDayTracker|g" \
    "${INSTALL_DIR}/n1mm-fieldday-tracker.desktop" > "${DESKTOP_FILE}"
chmod +x "${DESKTOP_FILE}" 2>/dev/null || true
command -v update-desktop-database >/dev/null 2>&1 &&
  update-desktop-database "${HOME}/.local/share/applications" 2>/dev/null || true

echo "[4/4] Firewall (informatief)"
if command -v ufw >/dev/null 2>&1; then
  echo "    Draait N1MM op een ANDERE pc? Sta dan de UDP-poort toe, bv.:"
  echo "      sudo ufw allow 12060/udp"
else
  echo "    Geen ufw gevonden — normaal hoef je niets te doen."
fi

cat <<EOF

============================================================
 Klaar! Start het programma via je menu ("${APP_NAME}")
 of met het commando:  n1mm-fieldday-tracker

 Staat het commando niet in je PATH? Voeg dit toe aan
 ~/.bashrc :   export PATH="\$HOME/.local/bin:\$PATH"

 VERGEET N1MM NIET IN TE STELLEN:
   1. Config > Configure Ports, Mode Control, Audio, Other...
   2. Tabblad "Broadcast Data"
   3. Vink "Contacts" aan (niet Lookup)
   4. Bestemming: 127.0.0.1:12060
      (draait N1MM op een andere pc: het IP van DEZE pc,
       en zet in de tracker het luisteradres op 0.0.0.0)
   5. Contest: FDREG1

 Verwijderen kan later met:  ./install.sh --uninstall
============================================================
EOF
