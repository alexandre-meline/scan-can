#!/bin/bash
# Script de nettoyage pour les interfaces CAN
# Usage: ./cleanup_can.sh [interface]

set -e

# Couleurs pour l'affichage
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration par défaut
DEFAULT_INTERFACE="can0"
INTERFACE=${1:-$DEFAULT_INTERFACE}

# Fonction d'affichage avec couleurs
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Fonction pour vérifier les permissions root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "Ce script doit être exécuté en tant que root"
        log_info "Utilisez: sudo $0 $@"
        exit 1
    fi
}

# Fonction pour arrêter une interface CAN spécifique
stop_can_interface() {
    local iface=$1
    
    log_info "Arrêt de l'interface CAN $iface..."
    
    # Vérifier si l'interface existe
    if ! ip link show "$iface" >/dev/null 2>&1; then
        log_warning "Interface $iface non trouvée"
        return 1
    fi
    
    # Arrêter l'interface
    if ip link show "$iface" | grep -q "UP"; then
        log_info "Désactivation de l'interface $iface"
        ip link set down "$iface" 2>/dev/null || {
            log_warning "Impossible de désactiver $iface"
        }
    else
        log_info "Interface $iface déjà désactivée"
    fi
    
    # Pour les interfaces slcan (USB), les supprimer complètement
    if ip link show "$iface" | grep -q "slcan"; then
        log_info "Suppression de l'interface slcan $iface"
        ip link delete "$iface" 2>/dev/null || {
            log_warning "Impossible de supprimer l'interface slcan $iface"
        }
    fi
    
    log_success "Interface $iface arrêtée"
}

# Fonction pour arrêter toutes les interfaces CAN
stop_all_can_interfaces() {
    log_info "Arrêt de toutes les interfaces CAN..."
    
    # Trouver toutes les interfaces CAN actives
    local can_interfaces
    can_interfaces=$(ip link show | grep -o 'can[0-9]*' | sort -u)
    
    if [[ -z "$can_interfaces" ]]; then
        log_info "Aucune interface CAN trouvée"
        return 0
    fi
    
    for iface in $can_interfaces; do
        stop_can_interface "$iface"
    done
}

# Fonction pour tuer les processus CAN en cours
kill_can_processes() {
    log_info "Arrêt des processus CAN en cours..."
    
    # Processus à arrêter
    processes=("candump" "cansend" "canplayer" "slcand")
    
    for process in "${processes[@]}"; do
        local pids
        pids=$(pgrep "$process" 2>/dev/null || true)
        
        if [[ -n "$pids" ]]; then
            log_info "Arrêt du processus $process (PIDs: $pids)"
            pkill "$process" 2>/dev/null || true
            sleep 1
            
            # Vérifier si le processus est toujours actif
            if pgrep "$process" >/dev/null 2>&1; then
                log_warning "Force kill du processus $process"
                pkill -9 "$process" 2>/dev/null || true
            fi
        fi
    done
}

# Fonction pour décharger les modules CAN (optionnel)
unload_can_modules() {
    log_info "Déchargement des modules CAN..."
    
    # Modules à décharger (dans l'ordre inverse de chargement)
    modules=("slcan" "vcan" "can_bcm" "can_raw" "can")
    
    for module in "${modules[@]}"; do
        if lsmod | grep -q "^$module "; then
            log_info "Déchargement du module $module"
            rmmod "$module" 2>/dev/null || {
                log_warning "Impossible de décharger le module $module (peut-être en cours d'utilisation)"
            }
        fi
    done
}

# Fonction pour nettoyer les fichiers temporaires
cleanup_temp_files() {
    log_info "Nettoyage des fichiers temporaires..."
    
    # Nettoyer les sockets CAN temporaires
    if [[ -d /tmp ]]; then
        find /tmp -name "can*" -type s 2>/dev/null | while read -r socket; do
            log_info "Suppression du socket temporaire: $socket"
            rm -f "$socket"
        done
    fi
    
    # Nettoyer les lock files
    lock_files=("/var/lock/slcan*" "/tmp/can*.lock")
    for pattern in "${lock_files[@]}"; do
        for file in $pattern; do
            if [[ -f "$file" ]]; then
                log_info "Suppression du fichier de verrou: $file"
                rm -f "$file"
            fi
        done
    done
}

# Fonction pour afficher le statut après nettoyage
show_cleanup_status() {
    log_info "Statut après nettoyage:"
    echo ""
    
    # Interfaces CAN restantes
    local remaining_interfaces
    remaining_interfaces=$(ip link show | grep -o 'can[0-9]*' | sort -u || true)
    
    if [[ -n "$remaining_interfaces" ]]; then
        log_warning "Interfaces CAN encore présentes:"
        for iface in $remaining_interfaces; do
            echo "  - $iface: $(ip link show "$iface" | grep -o 'state [A-Z]*' || echo 'état inconnu')"
        done
    else
        log_success "Aucune interface CAN active"
    fi
    
    echo ""
    
    # Processus CAN restants
    local remaining_processes
    remaining_processes=$(pgrep -f "can|slcan" 2>/dev/null || true)
    
    if [[ -n "$remaining_processes" ]]; then
        log_warning "Processus CAN encore actifs:"
        ps -p $remaining_processes -o pid,cmd 2>/dev/null || true
    else
        log_success "Aucun processus CAN actif"
    fi
    
    echo ""
    
    # Modules CAN chargés
    local can_modules
    can_modules=$(lsmod | grep can || true)
    
    if [[ -n "$can_modules" ]]; then
        log_info "Modules CAN encore chargés:"
        echo "$can_modules"
    else
        log_success "Aucun module CAN chargé"
    fi
}

# Fonction d'affichage de l'aide
show_help() {
    echo "Usage: $0 [INTERFACE] [OPTIONS]"
    echo ""
    echo "Nettoyage des interfaces et processus CAN-Bus"
    echo ""
    echo "Paramètres:"
    echo "  INTERFACE    Interface CAN à arrêter (défaut: $DEFAULT_INTERFACE)"
    echo "               Utilisez 'all' pour toutes les interfaces"
    echo ""
    echo "Options:"
    echo "  -h, --help           Afficher cette aide"
    echo "  --all                Arrêter toutes les interfaces CAN"
    echo "  --kill-processes     Tuer tous les processus CAN"
    echo "  --unload-modules     Décharger les modules CAN du kernel"
    echo "  --full-cleanup       Nettoyage complet (tout ce qui précède)"
    echo "  --status             Afficher le statut avant nettoyage"
    echo ""
    echo "Exemples:"
    echo "  $0                     # Arrêter can0"
    echo "  $0 can1                # Arrêter can1"
    echo "  $0 --all               # Arrêter toutes les interfaces"
    echo "  $0 --full-cleanup      # Nettoyage complet"
    echo "  $0 --status            # Statut actuel"
}

# Programme principal
main() {
    echo "=== Nettoyage CAN-Bus ==="
    echo ""
    
    # Variables pour les options
    STOP_ALL=false
    KILL_PROCESSES=false
    UNLOAD_MODULES=false
    FULL_CLEANUP=false
    SHOW_STATUS=false
    
    # Parser les arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            --all)
                STOP_ALL=true
                shift
                ;;
            --kill-processes)
                KILL_PROCESSES=true
                shift
                ;;
            --unload-modules)
                UNLOAD_MODULES=true
                shift
                ;;
            --full-cleanup)
                FULL_CLEANUP=true
                shift
                ;;
            --status)
                SHOW_STATUS=true
                shift
                ;;
            all)
                STOP_ALL=true
                shift
                ;;
            *)
                INTERFACE="$1"
                shift
                ;;
        esac
    done
    
    # Afficher le statut si demandé
    if [[ "$SHOW_STATUS" == true ]]; then
        show_cleanup_status
        exit 0
    fi
    
    # Vérifier les permissions root
    check_root "$@"
    
    log_info "Interface cible: $INTERFACE"
    echo ""
    
    # Nettoyage complet
    if [[ "$FULL_CLEANUP" == true ]]; then
        STOP_ALL=true
        KILL_PROCESSES=true
        UNLOAD_MODULES=true
    fi
    
    # Tuer les processus si demandé
    if [[ "$KILL_PROCESSES" == true ]]; then
        kill_can_processes
    fi
    
    # Arrêter les interfaces
    if [[ "$STOP_ALL" == true ]]; then
        stop_all_can_interfaces
    else
        stop_can_interface "$INTERFACE"
    fi
    
    # Nettoyer les fichiers temporaires
    cleanup_temp_files
    
    # Décharger les modules si demandé
    if [[ "$UNLOAD_MODULES" == true ]]; then
        unload_can_modules
    fi
    
    echo ""
    log_success "Nettoyage terminé!"
    echo ""
    
    # Afficher le statut final
    show_cleanup_status
    
    echo ""
    log_info "Pour redémarrer les interfaces CAN:"
    log_info "  sudo ./setup_can.sh"
}

# Exécuter le programme principal
main "$@"