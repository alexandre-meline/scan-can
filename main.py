#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import can, isotp, sys, time, argparse, logging, os
from datetime import datetime

# --- Config ---
CAN_IFACE = "can0"
TXID = 0x7E0
RXID = 0x7E8


def setup_logging(log_file=None, verbose=False):
    """Configure le système de logging"""
    log_format = '%(asctime)s - %(levelname)s - %(message)s'
    level = logging.DEBUG if verbose else logging.INFO
    
    handlers = [logging.StreamHandler()]
    if log_file:
        handlers.append(logging.FileHandler(log_file))
    
    logging.basicConfig(
        level=level,
        format=log_format,
        handlers=handlers
    )


def log_dtcs(dtcs, log_file=None):
    """Enregistre les DTC dans un fichier de log"""
    if not dtcs or not log_file:
        return
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f"\n=== Scan DTC - {timestamp} ===\n")
        if dtcs:
            f.write(f"DTC trouvés: {', '.join(dtcs)}\n")
        else:
            f.write("Aucun DTC trouvé\n")
        f.write("-" * 40 + "\n")


def parse_arguments():
    """Parse les arguments de la ligne de commande"""
    parser = argparse.ArgumentParser(
        description="Lecteur/Effaceur de codes DTC via CAN-Bus OBD-II"
    )
    
    parser.add_argument(
        '-i', '--interface',
        default='can0',
        help='Interface CAN à utiliser (défaut: can0)'
    )
    
    parser.add_argument(
        '-t', '--txid',
        type=lambda x: int(x, 0),
        default=0x7E0,
        help='ID CAN pour transmission (défaut: 0x7E0)'
    )
    
    parser.add_argument(
        '-r', '--rxid',
        type=lambda x: int(x, 0),
        default=0x7E8,
        help='ID CAN pour réception (défaut: 0x7E8)'
    )
    
    parser.add_argument(
        '-c', '--clear',
        action='store_true',
        help='Effacer les DTC après lecture'
    )
    
    parser.add_argument(
        '-l', '--log-file',
        help='Fichier de log pour enregistrer les DTC'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Mode verbeux'
    )
    
    parser.add_argument(
        '--timeout',
        type=float,
        default=2.0,
        help='Timeout pour les requêtes (défaut: 2.0s)'
    )
    
    parser.add_argument(
        '--no-scan',
        action='store_true',
        help='Ne pas scanner les DTC, seulement les effacer'
    )
    
    return parser.parse_args()


def decode_obd_dtc(data_bytes):
    # Réponse Mode 03 = 0x43, puis paires (2 octets) par DTC
    # Encodage SAE: premier nibble => P/C/B/U
    if not data_bytes or data_bytes[0] != 0x43:
        return []
    dtcs = []
    payload = data_bytes[1:]
    for i in range(0, len(payload), 2):
        if i + 1 >= len(payload):
            break
        b1, b2 = payload[i], payload[i + 1]
        if b1 == 0 and b2 == 0:
            continue
        # décodage P0xxx/C0xxx/B0xxx/U0xxx
        sys_code_map = {0: "P", 1: "C", 2: "B", 3: "U"}
        sys_code = sys_code_map[(b1 & 0xC0) >> 6]
        digit1 = (b1 & 0x30) >> 4
        digit2 = b1 & 0x0F
        digit3 = (b2 & 0xF0) >> 4
        digit4 = b2 & 0x0F
        dtc = f"{sys_code}{digit1}{digit2}{digit3}{digit4}"
        dtcs.append(dtc)
    return dtcs


def make_stack(bus, txid, rxid):
    addr = isotp.Address(
        isotp.AddressingMode.Normal_11bits, 
        txid=txid, 
        rxid=rxid
    )
    stack = isotp.CanStack(
        bus=bus,
        address=addr,
        error_handler=None,
        params={
            "tx_padding": 0x00,
            "rx_flowcontrol_timeout": 1000,
            "rx_consecutive_frame_timeout": 1000,
        },
    )
    return stack


def isotp_request(stack, payload, timeout=2.0):
    stack.send(payload)
    t0 = time.time()
    while time.time() - t0 < timeout:
        stack.process()
        time.sleep(0.01)
        if stack.available():
            resp = stack.recv()
            return resp
    return None


def main():
    # Parse des arguments
    args = parse_arguments()
    
    # Configuration du logging
    setup_logging(args.log_file, args.verbose)
    
    # Configuration des paramètres CAN
    can_iface = args.interface
    txid = args.txid
    rxid = args.rxid
    timeout = args.timeout
    
    logging.info(f"Ouverture {can_iface} @ 500k")
    logging.info(f"TX ID: 0x{txid:03X}, RX ID: 0x{rxid:03X}")
    
    try:
        bus = can.interface.Bus(can_iface, interface="socketcan")
        stack = make_stack(bus, txid, rxid)
    except Exception as e:
        logging.error(f"Erreur ouverture interface CAN: {e}")
        sys.exit(1)

    dtcs = []
    
    # LIRE DTC (Mode 03) - sauf si --no-scan
    if not args.no_scan:
        logging.info("Lecture des DTC (Mode 03)…")
        resp = isotp_request(stack, bytes([0x03]), timeout)
        
        if not resp:
            msg = ("Pas de réponse ECU "
                   "(contact mis ? bitrate 500k ? TX/RX IDs ?)")
            logging.error(msg)
            sys.exit(1)

        dtcs = decode_obd_dtc(list(resp))
        if dtcs:
            logging.info(f"DTC trouvés: {', '.join(dtcs)}")
            print(f"=> DTC trouvés : {', '.join(dtcs)}")
        else:
            logging.info("Aucun DTC stocké")
            print("=> Aucun DTC stocké")
            logging.debug(f"Réponse brute: {resp.hex()}")

        # Enregistrement dans le fichier de log
        if args.log_file:
            log_dtcs(dtcs, args.log_file)
            logging.info(f"DTC enregistrés dans {args.log_file}")

    # Effacement des DTC (Mode 04) - si demandé
    if args.clear or args.no_scan:
        if dtcs or args.no_scan:
            logging.info("Effacement des DTC (Mode 04)…")
            resp_clr = isotp_request(stack, bytes([0x04]), timeout)
            
            if resp_clr:
                if resp_clr[0] == 0x44:  # Réponse positive
                    logging.info("DTC effacés avec succès")
                    print("=> DTC effacés avec succès")
                else:
                    logging.warning(f"Réponse inattendue: {resp_clr.hex()}")
                    print(f"=> Réponse effacement: {resp_clr.hex()}")
            else:
                logging.error("Pas de réponse pour l'effacement")
                print("=> Aucune réponse pour l'effacement")
        else:
            logging.info("Aucun DTC à effacer")
            print("=> Aucun DTC à effacer")
    
    bus.shutdown()
    logging.info("Session terminée")


if __name__ == "__main__":
    main()
