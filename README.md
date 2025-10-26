# Scanner DTC CAN-Bus OBD-II 🚗🔧

**Suite complète d'outils pour le diagnostic automobile via CAN-Bus**

Ensemble d'outils Python et Bash pour lire, enregistrer et effacer les codes d'erreur (DTC) des véhicules via interface CAN-Bus utilisant le protocole OBD-II. Inclut une configuration automatisée et une gestion complète du cycle de vie des interfaces CAN.

## 📁 Structure du projet

```
scan-can/
├── main.py           # Scanner DTC principal (Python)
├── install.py        # Installation automatisée des dépendances
├── setup_can.sh      # Configuration automatique CAN-Bus
├── cleanup_can.sh    # Nettoyage et fermeture des interfaces CAN
├── README.md         # Documentation (ce fichier)
├── requirements.txt  # Dépendances Python (généré automatiquement)
├── venv/            # Environnement virtuel Python
└── dtc_log.txt      # Fichier de log des DTC (généré)
```

## 🚀 Installation rapide

### Option 1: Installation automatique (recommandée)
```bash
# Installation complète en une commande
python3 install.py

# Configuration CAN
sudo ./setup_can.sh

# Test
source venv/bin/activate
python main.py --help
```

### Option 2: Installation manuelle
```bash
# Créer l'environnement virtuel
python3 -m venv venv
source venv/bin/activate

# Installer les dépendances
pip install python-can can-isotp

# Configuration CAN manuelle
sudo modprobe can can_raw
sudo ip link set can0 type can bitrate 500000
sudo ip link set up can0
```

## 🛠️ Scripts disponibles

### 1. `install.py` - Installation automatisée
**Installation des dépendances Python et configuration de l'environnement**

```bash
# Installation standard
python3 install.py

# Options avancées
python3 install.py --venv-name mon_env      # Nom personnalisé pour l'environnement
python3 install.py --no-test               # Sans test d'installation
python3 install.py --system-check-only     # Vérification système uniquement
```

**Fonctionnalités :**
- Création automatique d'environnement virtuel
- Installation des dépendances Python
- Vérification des dépendances système
- Création de scripts d'activation
- Test de l'installation

### 2. `setup_can.sh` - Configuration CAN-Bus
**Configuration automatique des interfaces CAN**

```bash
# Configuration par défaut (can0, 500kbps)
sudo ./setup_can.sh

# Configuration personnalisée
sudo ./setup_can.sh can1 250000            # Interface can1 à 250k
sudo ./setup_can.sh --status               # Statut des interfaces
sudo ./setup_can.sh --test-only            # Test seulement
sudo ./setup_can.sh --no-service           # Sans service systemd
```

**Fonctionnalités :**
- Détection automatique d'adaptateurs USB CAN
- Configuration interface CAN native ou virtuelle
- Installation automatique de can-utils
- Création de service systemd pour auto-démarrage
- Support slcan pour adaptateurs USB
- Test de l'interface configurée

**Options :**
- `-h, --help` : Afficher l'aide
- `--status` : Statut des interfaces CAN
- `--test-only` : Tester l'interface existante
- `--no-service` : Ne pas créer le service systemd

### 3. `main.py` - Scanner DTC principal
**Lecture et effacement des codes d'erreur DTC**

```bash
# Activation de l'environnement
source venv/bin/activate

# Utilisation de base
python main.py                              # Lecture DTC simple
python main.py --help                       # Aide complète

# Exemples avancés
python main.py -l dtc_log.txt -v            # Avec logging verbeux
python main.py --clear --log-file history.txt  # Lecture + effacement + log
python main.py -i can1 -t 0x7DF -r 0x7E8    # Interface et IDs personnalisés
python main.py --no-scan --clear            # Effacement sans lecture
python main.py -v --timeout 5.0 --clear     # Timeout personnalisé
```

**Options complètes :**
- `-i, --interface` : Interface CAN (défaut: can0)
- `-t, --txid` : ID CAN transmission (défaut: 0x7E0)
- `-r, --rxid` : ID CAN réception (défaut: 0x7E8)
- `-c, --clear` : Effacer les DTC après lecture
- `-l, --log-file` : Fichier de log pour DTC
- `-v, --verbose` : Mode verbeux avec logging détaillé
- `--timeout` : Timeout requêtes en secondes (défaut: 2.0)
- `--no-scan` : Effacement seulement, pas de lecture

### 4. `cleanup_can.sh` - Nettoyage CAN
**Fermeture propre des interfaces et processus CAN**

```bash
# Nettoyage par défaut (can0)
sudo ./cleanup_can.sh

# Options de nettoyage
sudo ./cleanup_can.sh can1                  # Interface spécifique
sudo ./cleanup_can.sh --all                 # Toutes les interfaces
sudo ./cleanup_can.sh --full-cleanup        # Nettoyage complet
sudo ./cleanup_can.sh --status              # Statut avant nettoyage
```

**Fonctionnalités :**
- Arrêt propre des interfaces CAN
- Terminaison des processus CAN actifs
- Suppression des interfaces slcan (USB)
- Déchargement des modules kernel (optionnel)
- Nettoyage des fichiers temporaires
- Rapport de statut après nettoyage

**Options :**
- `--all` : Arrêter toutes les interfaces
- `--kill-processes` : Tuer tous les processus CAN
- `--unload-modules` : Décharger les modules kernel
- `--full-cleanup` : Nettoyage complet
- `--status` : Afficher le statut

## 📋 Workflow recommandé

### Premier démarrage
```bash
# 1. Installation
python3 install.py

# 2. Configuration CAN
sudo ./setup_can.sh

# 3. Test de base
source venv/bin/activate
python main.py -v

# 4. Nettoyage (optionnel)
sudo ./cleanup_can.sh
```

### Utilisation quotidienne
```bash
# Démarrage
sudo ./setup_can.sh can0 500000
source venv/bin/activate

# Diagnostic avec logging
python main.py -l diagnostic_$(date +%Y%m%d).txt -v

# Nettoyage après usage
sudo ./cleanup_can.sh --all
```

### Utilisation avancée
```bash
# Scanner et effacer sur interface custom
sudo ./setup_can.sh can1 250000
source venv/bin/activate
python main.py -i can1 -t 0x7DF -r 0x7E8 --clear -l custom_log.txt -v

# Nettoyage complet
sudo ./cleanup_can.sh --full-cleanup
```

## 📊 Format des logs

Le fichier de log contient un historique horodaté de tous les scans DTC :

```
=== Scan DTC - 2025-10-26 14:30:15 ===
DTC trouvés: P0171, P0300, U0100
----------------------------------------

=== Scan DTC - 2025-10-26 15:45:22 ===
Aucun DTC trouvé
----------------------------------------
```

## 🔍 Codes DTC supportés

Le scanner décode automatiquement les codes DTC au format SAE J2012 :

| Préfixe | Système | Description |
|---------|---------|-------------|
| **P** | Powertrain | Moteur, transmission, système de propulsion |
| **C** | Chassis | ABS, ESP, airbags, direction assistée |
| **B** | Body | Éclairage, climatisation, vitres électriques |
| **U** | Network | Communication CAN, réseaux de bord |

**Exemples courants :**
- `P0171` : Mélange trop pauvre (banque 1)
- `P0300` : Ratés d'allumage détectés
- `U0100` : Perte de communication avec l'ECU moteur
- `C1234` : Problème ABS/ESP

## 🖥️ Interfaces CAN supportées

### Adaptateurs USB CAN
- **PCAN-USB** (Peak Systems)
- **CANtact** (Linklayer Labs)
- **Kvaser** (gamme Leaf)
- **gs_usb** (compatible SocketCAN)
- **slcan** (adaptateurs série vers CAN)

### Interfaces intégrées
- **can0, can1...** (interfaces CAN natives Linux)
- **vcan** (interfaces virtuelles pour test)
- **Raspberry Pi CAN HAT**

### Configuration automatique
Le script `setup_can.sh` détecte automatiquement :
- Type d'adaptateur (USB vs natif)
- Port série pour adaptateurs USB
- Configuration optimale selon le matériel

## 🚨 Dépannage

### Problèmes courants

#### Pas de réponse ECU
```bash
# Vérifications de base
sudo ./setup_can.sh --status              # Statut des interfaces
python main.py -v --timeout 5.0           # Timeout plus long
```

**Causes possibles :**
- Contact véhicule non mis
- Mauvais bitrate (essayer 250k au lieu de 500k)
- IDs TX/RX incorrects
- Interface CAN mal configurée

#### Permission refusée
```bash
# Solution temporaire
sudo chmod 666 /dev/can0

# Solution permanente
sudo usermod -a -G dialout $USER
# Puis redémarrer la session
```

#### Interface non trouvée
```bash
# Lister les interfaces disponibles
ip link show

# Reconfigurer
sudo ./cleanup_can.sh --all
sudo ./setup_can.sh can0 500000
```

#### Modules CAN non chargés
```bash
# Chargement manuel
sudo modprobe can can_raw can_bcm

# Ou via le script
sudo ./setup_can.sh
```

### Messages d'erreur fréquents

| Erreur | Solution |
|--------|----------|
| `No such device` | Interface CAN non configurée → `sudo ./setup_can.sh` |
| `Permission denied` | Permissions insuffisantes → `sudo` ou groupe `dialout` |
| `Timeout` | ECU non accessible → vérifier contact véhicule |
| `Module not found` | Dépendances manquantes → `python3 install.py` |

## 🔧 Configuration avancée

### Variables d'environnement
```bash
export CAN_INTERFACE="can1"                # Interface par défaut
export CAN_BITRATE="250000"               # Bitrate par défaut
export DTC_LOG_DIR="/var/log/dtc"         # Répertoire logs
```

### IDs CAN personnalisés
Selon le constructeur et le type d'ECU :

| Constructeur | ECU | TX ID | RX ID |
|--------------|-----|-------|-------|
| Standard OBD-II | Moteur | 0x7E0 | 0x7E8 |
| Standard OBD-II | Broadcast | 0x7DF | 0x7E8-0x7EF |
| VAG/Audi/VW | Moteur | 0x7E0 | 0x7E8 |
| BMW | Moteur | 0x6F1 | 0x6F9 |
| Mercedes | Moteur | 0x7E0 | 0x7E8 |

### Service systemd personnalisé
Le script `setup_can.sh` peut créer un service systemd pour auto-démarrage :

```bash
# Activer le service
sudo ./setup_can.sh --create-service

# Gérer le service
sudo systemctl status can-setup
sudo systemctl stop can-setup
sudo systemctl disable can-setup
```

## 📚 Ressources supplémentaires

### Documentation technique
- [SocketCAN Linux](https://docs.kernel.org/networking/can.html)
- [ISO-TP Protocol](https://en.wikipedia.org/wiki/ISO-TP)
- [OBD-II Standards](https://en.wikipedia.org/wiki/OBD-II_PIDs)
- [SAE J1979](https://www.sae.org/standards/content/j1979_201408/)

### Outils complémentaires
```bash
# Surveillance en temps réel
candump can0

# Envoi de trames manuelles
cansend can0 7DF#0201050000000000

# Analyse de trafic
canlogger can0 -f logfile.txt

# Interface graphique
sudo apt install can-utils-extra
cansequence can0
```

## 🤝 Contribution

Pour contribuer au projet :

1. **Fork** le repository
2. Créer une **branche feature** (`git checkout -b feature/AmazingFeature`)
3. **Commit** les changements (`git commit -m 'Add some AmazingFeature'`)
4. **Push** sur la branche (`git push origin feature/AmazingFeature`)
5. Ouvrir une **Pull Request**

## 📄 Licence

Distribué sous licence MIT. Voir `LICENSE` pour plus d'informations.

## ⚠️ Avertissements

- **Utilisez uniquement sur vos propres véhicules** ou avec autorisation explicite
- **Testez d'abord en mode lecture** avant d'effacer des DTC
- **Sauvegardez toujours** les DTC avant effacement
- **Respectez les réglementations locales** concernant la modification des systèmes véhicules
- **Ce logiciel est fourni "tel quel"** sans garantie d'aucune sorte

---
*Développé avec ❤️ pour la communauté automobile open-source*