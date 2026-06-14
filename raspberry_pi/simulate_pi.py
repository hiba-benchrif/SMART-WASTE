"""
raspberry_pi/simulate_pi.py — Simulateur de Raspberry Pi pour les tests

Ce script simule le comportement de 3 poubelles sans matériel physique.
Il fonctionne sur Windows, Linux et macOS — aucun GPIO requis.
Idéal pour tester l'application sans Raspberry Pi.

Comportement simulé :
  - Chaque poubelle commence à un niveau différent
  - Le remplissage augmente de 0 à 5% par cycle (aléatoire)
  - Quand une poubelle atteint 95%, elle est "collectée" (remise à 0%)
  - Les données sont envoyées toutes les 30 secondes (configurable)

Usage :
    python raspberry_pi/simulate_pi.py

Configurable via variables d'environnement :
    NUM_BINS         : nombre de poubelles simulées (défaut: 3)
    INTERVAL_SECONDS : intervalle entre les envois (défaut: 30)
    SMARTWASTE_API_URL : URL de l'API (défaut: localhost:5000)
    SMARTWASTE_PI_API_KEY : clé API (défaut: dev-pi-secret-key-2024)
"""

import os
import time
import random
import sys
import logging
from datetime import datetime

# Charger les variables d'environnement
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env.example"))
except ImportError:
    pass

# Importer le module d'envoi
sys.path.insert(0, os.path.dirname(__file__))
from send_data import send_fill_level

# ── Configuration ──────────────────────────────────────────────────────────────
NUM_BINS         = int(os.getenv("NUM_BINS", "3"))
INTERVAL_SECONDS = int(os.getenv("INTERVAL_SECONDS", "30"))
API_URL          = os.getenv("SMARTWASTE_API_URL", "http://localhost:5000/api/bin-data")
API_KEY          = os.getenv("SMARTWASTE_PI_API_KEY", "dev-pi-secret-key-2024")

# Codes couleurs ANSI pour le terminal (Windows 10+ supporte ANSI)
class Color:
    GREEN  = "\033[92m"
    YELLOW = "\033[93m"
    RED    = "\033[91m"
    CYAN   = "\033[96m"
    BOLD   = "\033[1m"
    RESET  = "\033[0m"

def colored(text: str, color: str) -> str:
    """Applique une couleur ANSI au texte (avec fallback sans couleur)."""
    try:
        return f"{color}{text}{Color.RESET}"
    except Exception:
        return text


def get_status_label(fill: float) -> str:
    """Retourne un label coloré selon le niveau de remplissage."""
    if fill < 50:
        return colored("🟢 DISPONIBLE", Color.GREEN)
    elif fill < 80:
        return colored("🟡 MI-REMPLIE", Color.YELLOW)
    else:
        return colored("🔴 CRITIQUE  ", Color.RED)


def print_status_bar(fill: float, width: int = 30) -> str:
    """Génère une barre de progression ASCII."""
    filled = int(fill / 100 * width)
    bar = "█" * filled + "░" * (width - filled)
    color = Color.GREEN if fill < 50 else Color.YELLOW if fill < 80 else Color.RED
    return colored(f"[{bar}]", color)


def run_simulation():
    """
    Boucle principale de simulation.

    Initialise l'état de chaque poubelle et envoie les données
    au serveur à intervalle régulier.
    """
    # Initialisation des niveaux de remplissage (un par poubelle)
    # Les poubelles des bins 1..NUM_BINS dans la base de données
    fills = {i + 1: random.uniform(10, 60) for i in range(NUM_BINS)}

    print(colored("\n" + "═" * 60, Color.CYAN))
    print(colored("   SmartWaste — Simulateur Raspberry Pi", Color.BOLD))
    print(colored("═" * 60, Color.CYAN))
    print(f"   🗑️  Poubelles simulées : {NUM_BINS}")
    print(f"   ⏱️  Intervalle d'envoi : {INTERVAL_SECONDS}s")
    print(f"   🌐  Serveur API       : {API_URL}")
    print(colored("═" * 60 + "\n", Color.CYAN))
    print("Appuyez sur Ctrl+C pour arrêter\n")

    cycle = 0
    while True:
        cycle += 1
        ts = datetime.now().strftime("%H:%M:%S")
        print(colored(f"── Cycle #{cycle} — {ts} " + "─" * 35, Color.CYAN))

        for bin_id in range(1, NUM_BINS + 1):
            # Simulation du remplissage : +0 à +5% par cycle
            increase = random.uniform(0.5, 5.0)
            fills[bin_id] = round(min(fills[bin_id] + increase, 100), 1)

            current_fill = fills[bin_id]
            dist_cm      = round(60 * (1 - current_fill / 100), 1)

            # Affichage dans le terminal
            bar    = print_status_bar(current_fill)
            status = get_status_label(current_fill)
            print(f"  Poubelle #{bin_id}  {bar}  {current_fill:5.1f}%  {status}")

            # Envoi au serveur
            success = send_fill_level(
                bin_id=bin_id,
                fill_percentage=current_fill,
                distance_cm=dist_cm,
                api_url=API_URL,
                api_key=API_KEY,
                max_retries=2,
            )

            if not success:
                print(colored(f"  ⚠️  Envoi échoué pour la poubelle #{bin_id}", Color.YELLOW))

            # Simulation d'une collecte automatique si la poubelle est pleine
            if fills[bin_id] >= 95:
                print(colored(f"  🚛 Collecte simulée de la poubelle #{bin_id}", Color.GREEN))
                fills[bin_id] = random.uniform(0, 10)

        print(f"\n  ⏳ Prochaine mesure dans {INTERVAL_SECONDS}s...\n")
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    # Activer les couleurs ANSI et configurer l'encodage UTF-8 sur Windows
    if sys.platform == "win32":
        os.system("color")
        try:
            import io
            sys.stdout.reconfigure(encoding='utf-8')
        except AttributeError:
            pass

    try:
        run_simulation()
    except KeyboardInterrupt:
        print(colored("\n\n✅ Simulation arrêtée proprement.", Color.GREEN))
