#!/bin/bash
# Automated script for CAN-Bus setup
# Usage: ./setup_can.sh [interface] [bitrate]

set -e  # Stop on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Defaults
DEFAULT_INTERFACE="can0"
DEFAULT_BITRATE="500000"
DEFAULT_SAMPLE_POINT="0.875"

# Parameters
INTERFACE=${1:-$DEFAULT_INTERFACE}
BITRATE=${2:-$DEFAULT_BITRATE}
SAMPLE_POINT=${3:-$DEFAULT_SAMPLE_POINT}

# Function to display messages with colors
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

# Function to check for root permissions
check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root"
        log_info "Usage: sudo $0 $@"
        exit 1
    fi
}

# Function to load CAN modules
load_can_modules() {
    log_info "Loading CAN modules..."
    
    modules=("can" "can_raw" "can_bcm" "vcan")
    
    for module in "${modules[@]}"; do
        if ! lsmod | grep -q "^$module "; then
            log_info "Loading module $module"
            modprobe "$module" || {
                log_warning "Failed to load module $module"
            }
        else
            log_info "Module $module already loaded"
        fi
    done
}

# Function to detect USB CAN adapters
detect_usb_can() {
    log_info "DDetecting USB CAN adapters..."
    
    # Chercher les adaptateurs CAN USB courants
    if lsusb | grep -i "slcan\|cantact\|gs_usb\|peak"; then
        log_success "USB CAN adapter detected"
        return 0
    elif lsusb | grep -E "(1d50:606f|1209:0001|0c72:000c)"; then
        log_success "Compatible CAN adapter detected"
        return 0
    else
        log_warning "No USB CAN adapter recognized automatically"
        return 1
    fi
}

# Function to setup CAN interface
setup_can_interface() {
    log_info "Setting up CAN interface $INTERFACE..."
    
    # Stop the interface if it already exists
    if ip link show "$INTERFACE" >/dev/null 2>&1; then
        log_info "Stopping existing interface $INTERFACE"
        ip link set down "$INTERFACE" 2>/dev/null || true
        ip link delete "$INTERFACE" 2>/dev/null || true
    fi

    # For USB adapters (slcan)
    if detect_usb_can; then
        log_info "Configuration pour adaptateur USB..."
        
        # Find the serial port
        for port in /dev/ttyUSB* /dev/ttyACM*; do
            if [[ -e $port ]]; then
                log_info "Attempting configuration on $port"

                # Configure slcan
                slcand -o -c -s6 "$port" "$INTERFACE" 2>/dev/null && {
                    sleep 1
                    ip link set up "$INTERFACE"
                    log_success "Interface $INTERFACE configured via $port"
                    return 0
                } || {
                    log_warning "Failed to configure on $port"
                }
            fi
        done
    fi
    
    # Native CAN interface
    log_info "Setting up native CAN interface..."

    # Create the interface if it doesn't exist
    if ! ip link show "$INTERFACE" >/dev/null 2>&1; then
        # Try to create a virtual interface for testing
        log_info "Creating virtual CAN interface for testing"
        modprobe vcan
        ip link add dev "$INTERFACE" type vcan
    fi

    # Configure CAN parameters
    if ip link show "$INTERFACE" >/dev/null 2>&1; then
        log_info "Setting up parameters: bitrate=$BITRATE, sample-point=$SAMPLE_POINT"

        # For physical interface
        ip link set "$INTERFACE" type can bitrate "$BITRATE" sample-point "$SAMPLE_POINT" 2>/dev/null || {
            # For virtual interface
            log_info "Setting up in virtual mode"
        }

        # Activate the interface
        ip link set up "$INTERFACE"
        log_success "Interface $INTERFACE activated"
    else
        log_error "Failed to create interface $INTERFACE"
        return 1
    fi
}

# Function to test the CAN interface
test_can_interface() {
    log_info "Testing CAN interface $INTERFACE..."

    # Check if the interface is up
    if ip link show "$INTERFACE" | grep -q "UP"; then
        log_success "Interface $INTERFACE is up"

        # Show statistics
        if command -v cansend >/dev/null 2>&1; then
            log_info "Testing CAN send (test frame)..."
            timeout 2 cansend "$INTERFACE" 123#DEADBEEF 2>/dev/null && {
                log_success "Send test successful"
            } || {
                log_warning "Send test failed (normal if no physical bus)"
            }
        fi

        # Show interface information
        log_info "Interface information:"
        ip -details link show "$INTERFACE"
        
        return 0
    else
        log_error "Interface $INTERFACE is not up"
        return 1
    fi
}

# Function to configure permissions
setup_permissions() {
    log_info "Configuring permissions..."
    
    # Add user to dialout group if necessary
    if [[ -n "${SUDO_USER:-}" ]]; then
        usermod -a -G dialout "$SUDO_USER" 2>/dev/null || true
        log_info "User $SUDO_USER added to dialout group"
    fi

    # Permissions on the interface
    if [[ -e "/dev/$INTERFACE" ]]; then
        chmod 666 "/dev/$INTERFACE"
        log_success "Permissions configured for /dev/$INTERFACE"
    fi
}

# Function to install CAN tools
install_can_tools() {
    log_info "Checking CAN tools..."

    # Detect package manager
    if command -v apt-get >/dev/null 2>&1; then
        PKG_MANAGER="apt-get"
        PACKAGES="can-utils"
    elif command -v yum >/dev/null 2>&1; then
        PKG_MANAGER="yum"
        PACKAGES="can-utils"
    elif command -v pacman >/dev/null 2>&1; then
        PKG_MANAGER="pacman"
        PACKAGES="can-utils"
    else
        log_warning "Unknown package manager. Please install can-utils manually."
        return 1
    fi
    
    # Install can-utils if necessary
    if ! command -v cansend >/dev/null 2>&1; then
        log_info "Installing can-utils..."
        case $PKG_MANAGER in
            "apt-get")
                apt-get update && apt-get install -y $PACKAGES
                ;;
            "yum")
                yum install -y $PACKAGES
                ;;
            "pacman")
                pacman -S --noconfirm $PACKAGES
                ;;
        esac
        log_success "CAN tools installed"
    else
        log_success "CAN tools already installed"
    fi
}

# Function to create a systemd service
create_systemd_service() {
    log_info "Creating systemd service for CAN auto-configuration..."

    cat > "/etc/systemd/system/can-setup.service" << EOF
[Unit]
Description=CAN Bus Interface Setup
After=network.target
Wants=network.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=$PWD/setup_can.sh $INTERFACE $BITRATE
User=root

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable can-setup.service
    log_success "Service systemd créé et activé"
}

# Function to display help
show_help() {
    echo "Usage: $0 [INTERFACE] [BITRATE] [OPTIONS]"
    echo ""
    echo "Automatic CAN-Bus interface configuration script."
    echo ""
    echo "Parameters:"
    echo "  INTERFACE    CAN interface (default: $DEFAULT_INTERFACE)"
    echo "  BITRATE      Bitrate in bps (default: $DEFAULT_BITRATE)"
    echo ""
    echo "Options:"
    echo "  -h, --help       Display this help"
    echo "  --no-service     Do not create systemd service"
    echo "  --test-only      Only test existing interface"
    echo "  --status         Show status of CAN interfaces"
    echo ""
    echo "Examples:"
    echo "  $0                    # Default configuration (can0, 500k)"
    echo "  $0 can1 250000        # Interface can1 at 250k"
    echo "  $0 --status           # Status of interfaces"
    echo "  $0 --test-only        # Test only"
}

# Function to display status
show_status() {
    log_info "Status of CAN interfaces:"
    echo ""

    # List all CAN interfaces
    for iface in $(ip link show | grep -o 'can[0-9]*' | sort -u); do
        echo "Interface: $iface"
        ip -details link show "$iface" 2>/dev/null || echo "  Not configured"
        echo ""
    done

    # Loaded modules
    echo "Loaded CAN modules:"
    lsmod | grep can || echo "  No CAN modules loaded"
    echo ""

    # USB adapters
    echo "Detected USB CAN adapters:"
    lsusb | grep -i "slcan\|cantact\|gs_usb\|peak" || echo "  No adapters detected"
}

# Main program
main() {
    echo "=== Automatic CAN-Bus Configuration ==="
    echo ""

    # Variables for options
    NO_SERVICE=false
    TEST_ONLY=false
    SHOW_STATUS=false

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            --no-service)
                NO_SERVICE=true
                shift
                ;;
            --test-only)
                TEST_ONLY=true
                shift
                ;;
            --status)
                SHOW_STATUS=true
                shift
                ;;
            *)
                # Positional arguments
                if [[ -z "${INTERFACE_SET:-}" ]]; then
                    INTERFACE="$1"
                    INTERFACE_SET=true
                elif [[ -z "${BITRATE_SET:-}" ]]; then
                    BITRATE="$1"
                    BITRATE_SET=true
                fi
                shift
                ;;
        esac
    done

    # Show status if requested
    if [[ "$SHOW_STATUS" == true ]]; then
        show_status
        exit 0
    fi

    # Check root permissions
    check_root "$@"
    
    log_info "Configuration: Interface=$INTERFACE, Bitrate=$BITRATE"
    echo ""
    
    # Test only mode
    if [[ "$TEST_ONLY" == true ]]; then
        test_can_interface
        exit $?
    fi

    # Full configuration process
    install_can_tools
    load_can_modules
    setup_can_interface
    setup_permissions
    test_can_interface
    
    # Create systemd service if requested
    if [[ "$NO_SERVICE" != true ]]; then
        create_systemd_service
    fi
    
    echo ""
    log_success "Configuration CAN finished successfully!"
    log_info "Interface $INTERFACE configured to $BITRATE bps"
    log_info "You can now use the DTC scanner"
    echo ""
    log_info "Useful commands:"
    echo "  ip link show $INTERFACE              # Status of the interface"
    echo "  candump $INTERFACE                   # Listen to CAN traffic"
    echo "  cansend $INTERFACE 123#DEADBEEF      # Send a test frame"
    echo "  python3 main.py -i $INTERFACE -v    # Start the DTC scanner"
}

# Run the main program
main "$@"