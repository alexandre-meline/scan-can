#!/usr/bin/env python3
"""
Script d'installation et de configuration pour le scanner DTC CAN-Bus
Automatise l'installation des dépendances Python et la configuration de l'environnement
"""

import os
import sys
import subprocess
import argparse
import venv
from pathlib import Path

def run_command(cmd, check=True, shell=False):
    """Exécute une commande et retourne le résultat"""
    try:
        if shell:
            result = subprocess.run(cmd, shell=True, check=check, 
                                  capture_output=True, text=True)
        else:
            result = subprocess.run(cmd, check=check, 
                                  capture_output=True, text=True)
        return result
    except subprocess.CalledProcessError as e:
        print(f"Erreur lors de l'exécution de: {' '.join(cmd) if not shell else cmd}")
        print(f"Code de retour: {e.returncode}")
        print(f"Sortie d'erreur: {e.stderr}")
        if check:
            sys.exit(1)
        return e

def check_python_version():
    """Vérifie que Python 3.7+ est disponible"""
    if sys.version_info < (3, 7):
        print("❌ Python 3.7 ou supérieur requis")
        print(f"Version actuelle: {sys.version}")
        sys.exit(1)
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} détecté")

def create_virtual_environment(venv_path):
    """Crée un environnement virtuel Python"""
    print(f"📦 Création de l'environnement virtuel dans {venv_path}...")
    
    if venv_path.exists():
        print(f"⚠️  L'environnement virtuel existe déjà dans {venv_path}")
        response = input("Voulez-vous le recréer? (y/N): ").lower().strip()
        if response == 'y':
            import shutil
            shutil.rmtree(venv_path)
        else:
            print("ℹ️  Utilisation de l'environnement existant")
            return venv_path
    
    try:
        venv.create(venv_path, with_pip=True)
        print("✅ Environnement virtuel créé")
        return venv_path
    except Exception as e:
        print(f"❌ Erreur lors de la création de l'environnement virtuel: {e}")
        sys.exit(1)

def get_pip_path(venv_path):
    """Retourne le chemin vers pip dans l'environnement virtuel"""
    if os.name == 'nt':  # Windows
        return venv_path / "Scripts" / "pip"
    else:  # Unix/Linux/macOS
        return venv_path / "bin" / "pip"

def get_python_path(venv_path):
    """Retourne le chemin vers python dans l'environnement virtuel"""
    if os.name == 'nt':  # Windows
        return venv_path / "Scripts" / "python"
    else:  # Unix/Linux/macOS
        return venv_path / "bin" / "python"

def install_python_dependencies(venv_path):
    """Installe les dépendances Python dans l'environnement virtuel"""
    pip_path = get_pip_path(venv_path)
    
    # Mise à jour de pip
    print("🔄 Mise à jour de pip...")
    run_command([str(pip_path), "install", "--upgrade", "pip"])
    
    # Dépendances principales
    dependencies = [
        "python-can>=4.0.0",
        "can-isotp>=2.0.0",
    ]
    
    # Dépendances optionnelles pour de meilleures fonctionnalités
    optional_dependencies = [
        "colorama",  # Pour les couleurs sur Windows
        "psutil",    # Pour la détection système
    ]
    
    print("📦 Installation des dépendances principales...")
    for dep in dependencies:
        print(f"   Installing {dep}...")
        run_command([str(pip_path), "install", dep])
    
    print("📦 Installation des dépendances optionnelles...")
    for dep in optional_dependencies:
        print(f"   Installing {dep}...")
        # Ne pas échouer si les dépendances optionnelles ne s'installent pas
        run_command([str(pip_path), "install", dep], check=False)
    
    print("✅ Dépendances Python installées")

def create_activation_script(venv_path, project_path):
    """Crée un script d'activation pratique"""
    script_content = f"""#!/bin/bash
# Script d'activation pour le scanner DTC CAN-Bus

SCRIPT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
VENV_PATH="{venv_path}"

echo "🚀 Activation de l'environnement de développement..."

# Activer l'environnement virtuel
source "$VENV_PATH/bin/activate"

# Changer vers le répertoire du projet
cd "$SCRIPT_DIR"

echo "✅ Environnement activé!"
echo "📁 Répertoire: $(pwd)"
echo "🐍 Python: $(which python)"
echo ""
echo "Commandes disponibles:"
echo "  python main.py --help           # Aide du scanner DTC"
echo "  sudo ./setup_can.sh --help      # Aide configuration CAN"
echo "  sudo ./setup_can.sh --status    # Statut des interfaces CAN"
echo "  deactivate                      # Désactiver l'environnement"
echo ""

# Lancer un shell interactif
exec bash
"""
    
    activate_script = project_path / "activate_env.sh"
    with open(activate_script, 'w') as f:
        f.write(script_content)
    
    os.chmod(activate_script, 0o755)
    print(f"✅ Script d'activation créé: {activate_script}")

def create_requirements_file(project_path):
    """Crée un fichier requirements.txt"""
    requirements_content = """# Dépendances pour le scanner DTC CAN-Bus
python-can>=4.0.0
can-isotp>=2.0.0

# Dépendances optionnelles
colorama>=0.4.0
psutil>=5.0.0
"""
    
    requirements_file = project_path / "requirements.txt"
    with open(requirements_file, 'w') as f:
        f.write(requirements_content)
    
    print(f"✅ Fichier requirements.txt créé")

def check_system_dependencies():
    """Vérifie les dépendances système"""
    print("🔍 Vérification des dépendances système...")
    
    # Vérifier can-utils
    try:
        result = run_command(["which", "cansend"], check=False)
        if result.returncode == 0:
            print("✅ can-utils installé")
        else:
            print("⚠️  can-utils non trouvé")
            print("   Installez avec: sudo apt-get install can-utils  (Ubuntu/Debian)")
            print("   Ou utilisez: sudo ./setup_can.sh  (installation automatique)")
    except:
        print("⚠️  Impossible de vérifier can-utils")
    
    # Vérifier les modules kernel CAN
    try:
        result = run_command(["lsmod"], check=False)
        if "can" in result.stdout:
            print("✅ Modules CAN kernel chargés")
        else:
            print("⚠️  Modules CAN kernel non chargés")
            print("   Chargez avec: sudo modprobe can can_raw")
            print("   Ou utilisez: sudo ./setup_can.sh  (configuration automatique)")
    except:
        print("⚠️  Impossible de vérifier les modules kernel")

def test_installation(venv_path):
    """Teste l'installation"""
    python_path = get_python_path(venv_path)
    
    print("🧪 Test de l'installation...")
    
    # Test d'import des modules
    test_script = '''
import sys
try:
    import can
    print("✅ python-can importé")
    print(f"   Version: {can.__version__}")
except ImportError as e:
    print(f"❌ Erreur import python-can: {e}")
    sys.exit(1)

try:
    import isotp
    print("✅ can-isotp importé")
    print(f"   Version: {isotp.__version__}")
except ImportError as e:
    print(f"❌ Erreur import can-isotp: {e}")
    sys.exit(1)

print("✅ Tous les modules sont importables")
'''
    
    try:
        result = run_command([str(python_path), "-c", test_script])
        print(result.stdout)
        print("✅ Test d'installation réussi")
    except Exception as e:
        print(f"❌ Test d'installation échoué: {e}")

def main():
    parser = argparse.ArgumentParser(
        description="Installation et configuration du scanner DTC CAN-Bus"
    )
    parser.add_argument(
        "--venv-name", 
        default="venv",
        help="Nom de l'environnement virtuel (défaut: venv)"
    )
    parser.add_argument(
        "--no-test",
        action="store_true",
        help="Ne pas tester l'installation"
    )
    parser.add_argument(
        "--system-check-only",
        action="store_true",
        help="Vérifier seulement les dépendances système"
    )
    
    args = parser.parse_args()
    
    # Déterminer les chemins
    project_path = Path(__file__).parent.absolute()
    venv_path = project_path / args.venv_name
    
    print("🔧 Installation du scanner DTC CAN-Bus")
    print(f"📁 Répertoire projet: {project_path}")
    print(f"🐍 Environnement virtuel: {venv_path}")
    print()
    
    # Vérification système uniquement
    if args.system_check_only:
        check_system_dependencies()
        return
    
    # Vérifications préliminaires
    check_python_version()
    check_system_dependencies()
    
    # Installation Python
    create_virtual_environment(venv_path)
    install_python_dependencies(venv_path)
    
    # Création des fichiers utiles
    create_requirements_file(project_path)
    create_activation_script(venv_path, project_path)
    
    # Test de l'installation
    if not args.no_test:
        test_installation(venv_path)
    
    print()
    print("🎉 Installation terminée avec succès!")
    print()
    print("📋 Prochaines étapes:")
    print(f"   1. Configuration CAN: sudo ./setup_can.sh")
    print(f"   2. Activation env:    source {venv_path}/bin/activate")
    print(f"   3. Ou utilisez:       ./activate_env.sh")
    print(f"   4. Test scanner:      python main.py --help")
    print()
    print("💡 Conseils:")
    print("   • Utilisez './activate_env.sh' pour un environnement prêt à l'emploi")
    print("   • Consultez le README.md pour plus d'informations")
    print("   • Utilisez 'sudo ./setup_can.sh --status' pour vérifier les interfaces CAN")

if __name__ == "__main__":
    main()