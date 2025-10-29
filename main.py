#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import time
import argparse
import logging
from datetime import datetime
from typing import Dict, Tuple, Callable, List, Optional
import can
import isotp

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

    # Lecture temps réel des PIDs OBD-II (Mode 01)
    parser.add_argument(
        '--live',
        action='store_true',
        help='Lire des PIDs OBD-II en temps réel (Mode 01)'
    )
    parser.add_argument(
        '--pids',
        default='rpm,speed,coolant,throttle',
        help='Liste de PIDs à lire (noms ou hex, séparés par des virgules). '
             'Ex: rpm,speed,coolant,throttle ou 0x0C,0x0D,0x05,0x11'
    )
    parser.add_argument(
        '--interval',
        type=float,
        default=0.5,
        help='Intervalle entre lectures en secondes (défaut: 0.5)'
    )
    parser.add_argument(
        '--duration',
        type=float,
        default=0.0,
        help='Durée totale en secondes (0 = illimitée)'
    )
    parser.add_argument(
        '--csv-file',
        help='Exporter les données live en CSV (fichier)'
    )

    # DTC avancés
    parser.add_argument(
        '--pending',
        action='store_true',
        help='Lire les DTC en attente (Mode 07)'
    )
    parser.add_argument(
        '--freeze',
        action='store_true',
        help='Lire le DTC ayant déclenché le freeze-frame (Mode 02)'
    )
    
    return parser.parse_args()


def _decode_dtc_pair(b1: int, b2: int) -> str:
    """Décoder deux octets en code DTC SAE (P/C/B/U)."""
    sys_code_map = {0: "P", 1: "C", 2: "B", 3: "U"}
    sys_code = sys_code_map[(b1 & 0xC0) >> 6]
    digit1 = (b1 & 0x30) >> 4
    digit2 = b1 & 0x0F
    digit3 = (b2 & 0xF0) >> 4
    digit4 = b2 & 0x0F
    return f"{sys_code}{digit1}{digit2}{digit3}{digit4}"


def decode_obd_dtc(data_bytes: List[int]) -> List[str]:
    """Décoder les DTC pour Mode 03 (0x43) et Mode 07 (0x47).

    Le payload contient des paires d'octets (2 par DTC).
    """
    if not data_bytes or data_bytes[0] not in (0x43, 0x47):
        return []
    dtcs: List[str] = []
    payload = data_bytes[1:]
    for i in range(0, len(payload), 2):
        if i + 1 >= len(payload):
            break
        b1, b2 = payload[i], payload[i + 1]
        if b1 == 0 and b2 == 0:
            continue
        dtc = _decode_dtc_pair(b1, b2)
        dtcs.append(dtc)
    return dtcs


def decode_freeze_frame_dtc(data_bytes: List[int]) -> List[str]:
    """Décoder le DTC ayant déclenché le freeze-frame (Mode 02 PID 0x02).

    Réponse attendue: [0x42, 0x02, A, B, ...] où A,B encodent le DTC.
    """
    if not data_bytes or len(data_bytes) < 4:
        return []
    if data_bytes[0] != 0x42 or data_bytes[1] != 0x02:
        return []
    b1, b2 = data_bytes[2], data_bytes[3]
    if b1 == 0 and b2 == 0:
        return []
    return [_decode_dtc_pair(b1, b2)]


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


# ==========================
# OBD-II Mode 01: Live PIDs
# ==========================

# PID definition: name: (pid, decode_fn, unit)
PIDDef = Tuple[int, Callable[[List[int]], Optional[float]], str]
PID_DEFS: Dict[str, PIDDef] = {
    # Température liquide de refroidissement (A - 40) °C
    'coolant': (
        0x05,
        lambda d: (d[0] - 40) if len(d) >= 1 else None,
        '°C'
    ),
    # Régime moteur (((A*256)+B)/4) rpm
    'rpm': (
        0x0C,
        lambda d: (((d[0] << 8) | d[1]) / 4) if len(d) >= 2 else None,
        'rpm'
    ),
    # Vitesse véhicule A km/h
    'speed': (
        0x0D,
        lambda d: d[0] if len(d) >= 1 else None,
        'km/h'
    ),
    # Température d'air admission (A - 40) °C
    'intake_temp': (
        0x0F,
        lambda d: (d[0] - 40) if len(d) >= 1 else None,
        '°C'
    ),
    # Débit d'air MAF (((A*256)+B)/100) g/s
    'maf': (
        0x10,
        lambda d: (((d[0] << 8) | d[1]) / 100) if len(d) >= 2 else None,
        'g/s'
    ),
    # Position papillon (A*100/255) %
    'throttle': (
        0x11,
        lambda d: (d[0] * 100 / 255) if len(d) >= 1 else None,
        '%'
    ),
    # Fuel trim court terme banque 1 ((A-128)/1.28) %
    'stft1': (
        0x06,
        lambda d: ((d[0] - 128) / 1.28) if len(d) >= 1 else None,
        '%'
    ),
    # Fuel trim long terme banque 1 ((A-128)/1.28) %
    'ltft1': (
        0x07,
        lambda d: ((d[0] - 128) / 1.28) if len(d) >= 1 else None,
        '%'
    ),
}


def parse_pid_list(pid_list_str: str) -> List[Tuple[str, int, str]]:
    """Convertit une chaîne de PIDs en liste de tuples (label, pid, unit)."""
    items = [x.strip() for x in pid_list_str.split(',') if x.strip()]
    result: List[Tuple[str, int, str]] = []
    for it in items:
        key = it.lower()
        if key in PID_DEFS:
            pid, _, unit = PID_DEFS[key]
            result.append((key, pid, unit))
        else:
            # Essayer de parser un hex
            try:
                pid = int(it, 0)
                label = f"pid_0x{pid:02X}"
                result.append((label, pid, ''))
            except ValueError:
                logging.warning(f"PID inconnu ignoré: {it}")
    return result


def request_pid(
    stack: isotp.CanStack,
    pid: int,
    timeout: float
) -> Optional[List[int]]:
    """Envoie une requête Mode 01 pour un PID et retourne la donnée brute
    (liste d'octets)."""
    resp = isotp_request(stack, bytes([0x01, pid]), timeout)
    if not resp:
        return None
    data = list(resp)
    if len(data) < 2:
        return None
    if data[0] != 0x41 or data[1] != pid:
        # Réponse inattendue
        return None
    return data[2:]


def decode_pid_value(label: str, raw: List[int]) -> Optional[float]:
    """Applique le décodage si connu, sinon None."""
    if label in PID_DEFS:
        _, fn, _ = PID_DEFS[label]
        try:
            return fn(raw)
        except Exception:
            return None
    return None


def live_read_loop(stack: isotp.CanStack,
                   pid_specs: List[Tuple[str, int, str]],
                   interval: float,
                   duration: float,
                   csv_path: Optional[str],
                   timeout: float) -> None:
    """Boucle de lecture live des PIDs et affichage/CSV."""
    start = time.time()
    header_written = False
    csv_file = None
    try:
        if csv_path:
            csv_file = open(csv_path, 'a', encoding='utf-8')
        while True:
            now = time.time()
            if duration > 0 and (now - start) >= duration:
                break
            row_ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            values_for_csv: List[str] = []
            line_parts: List[str] = []
            for label, pid, unit in pid_specs:
                raw = request_pid(stack, pid, timeout)
                val = decode_pid_value(label, raw) if raw is not None else None
                if val is not None:
                    display = f"{val:.2f}{unit}" if unit else f"{val:.2f}"
                else:
                    display = "NA"
                line_parts.append(f"{label}={display}")
                values_for_csv.append(display)

            # Console output
            print(f"[{row_ts}] " + " | ".join(line_parts))

            # CSV output
            if csv_file:
                if not header_written:
                    headers = ['timestamp'] + [
                        lbl for (lbl, _, _) in pid_specs
                    ]
                    csv_file.write(','.join(headers) + '\n')
                    header_written = True
                csv_file.write(','.join([row_ts] + values_for_csv) + '\n')
                csv_file.flush()

            time.sleep(max(0.05, interval))
    finally:
        if csv_file:
            csv_file.close()


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
    
    # LIVE PIDs
    if args.live:
        pid_specs = parse_pid_list(args.pids)
        if not pid_specs:
            logging.error("Aucun PID valide fourni")
            sys.exit(2)
        logging.info("Lecture live des PIDs (Mode 01)…")
        try:
            live_read_loop(
                stack,
                pid_specs,
                args.interval,
                args.duration,
                args.csv_file,
                timeout,
            )
        except KeyboardInterrupt:
            print("\nInterrompu par l'utilisateur")
        finally:
            bus.shutdown()
        logging.info("Session terminée (live)")
        return

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

        # DTC en attente (Mode 07)
        if args.pending:
            logging.info("Lecture des DTC en attente (Mode 07)…")
            resp_p = isotp_request(stack, bytes([0x07]), timeout)
            pend = decode_obd_dtc(list(resp_p)) if resp_p else []
            if pend:
                print(f"=> DTC en attente : {', '.join(pend)}")
            else:
                print("=> Aucun DTC en attente")

        # Freeze-frame DTC (Mode 02 PID 0x02)
        if args.freeze:
            logging.info("Lecture freeze-frame DTC (Mode 02)…")
            resp_ff = isotp_request(stack, bytes([0x02, 0x02]), timeout)
            ff = decode_freeze_frame_dtc(list(resp_ff)) if resp_ff else []
            if ff:
                print(f"=> DTC freeze-frame : {', '.join(ff)}")
            else:
                print("=> Aucun DTC freeze-frame disponible")

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
