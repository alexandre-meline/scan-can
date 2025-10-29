#!/bin/bash
# Enregistrer le trafic CAN avec horodatage
# Usage: ./record_can.sh [interface] [fichier] [--errors]

set -e

IFACE=${1:-can0}
OUT=${2:-can_${IFACE}_$(date +%Y%m%d_%H%M%S).log}
INCLUDE_ERRORS=false

if [[ "$3" == "--errors" ]]; then
  INCLUDE_ERRORS=true
fi

echo "[INFO] Enregistrement CAN sur $IFACE -> $OUT"

# Vérifier can-utils
if ! command -v candump >/dev/null 2>&1; then
  echo "[ERROR] can-utils n'est pas installé (candump manquant)" >&2
  echo "Installez-le via: sudo apt-get install can-utils" >&2
  exit 1
fi

# Options candump
# -t a : horodatage absolu
# -t z : horodatage relatif
# -e   : inclure les trames d'erreur
# -c   : couleur
# -a   : afficher les adresses ASCII

OPTS=("-t" "a")
if [[ "$INCLUDE_ERRORS" == true ]]; then
  OPTS+=("-e")
fi

# Enregistrer avec tee pour voir à l'écran et sauvegarder
set -o pipefail
candump "${OPTS[@]}" "$IFACE" | tee "$OUT"
