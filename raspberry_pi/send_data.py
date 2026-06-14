"""
raspberry_pi/send_data.py — Envoi des données au serveur SmartWaste

Ce script est responsable de l'envoi des mesures du capteur vers l'API.
Il est séparé de sensor.py pour respecter le principe de responsabilité unique.

Fonctionnalités :
  - Envoi HTTP POST vers /api/bin-data avec la clé API
  - Retry automatique avec backoff exponentiel (max 3 tentatives)
  - Journal local des envois dans data_log.txt
  - Retourne True/False selon le succès de l'envoi

Sécurité :
  - La clé API est lue depuis les variables d'environnement
  - Elle est envoyée dans l'en-tête X-API-KEY (jamais dans l'URL)
"""

import os
import time
import logging
import requests
from datetime import datetime
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── Configuration ──────────────────────────────────────────────────────────────
API_URL = os.getenv("SMARTWASTE_API_URL", "http://localhost:5000/api/bin-data")
API_KEY = os.getenv("SMARTWASTE_PI_API_KEY", "dev-pi-secret-key-2024")
BIN_ID  = int(os.getenv("SMARTWASTE_BIN_ID", "1"))
LOG_FILE = Path(__file__).parent / "data_log.txt"

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def log_to_file(bin_id: int, fill_percentage: float, status: str) -> None:
    """
    Enregistre une mesure dans le fichier journal local data_log.txt.

    Le journal local sert de sauvegarde au cas où le serveur serait
    temporairement inaccessible. Format CSV simple pour analyse ultérieure.

    Args:
        bin_id: Identifiant de la poubelle.
        fill_percentage: Niveau de remplissage mesuré.
        status: Résultat de l'envoi ('SUCCESS' ou 'FAILED').
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{timestamp},{bin_id},{fill_percentage:.1f},{status}\n"

    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)
    except IOError as e:
        logger.warning(f"Impossible d'écrire dans le journal : {e}")


def send_fill_level(
    bin_id: int,
    fill_percentage: float,
    distance_cm: float = None,
    api_url: str = None,
    api_key: str = None,
    max_retries: int = 3,
) -> bool:
    """
    Envoie le niveau de remplissage au serveur SmartWaste avec retry automatique.

    Stratégie de retry avec backoff exponentiel :
      - Tentative 1 : immédiate
      - Tentative 2 : après 2 secondes
      - Tentative 3 : après 4 secondes

    L'en-tête X-API-KEY authentifie le Raspberry Pi auprès du serveur.
    Le serveur vérifie la clé en comparant son hash SHA-256.

    Args:
        bin_id: Identifiant de la poubelle dans la base de données.
        fill_percentage: Niveau de remplissage (0-100%).
        distance_cm: Distance brute mesurée (optionnel).
        api_url: URL de l'API (défaut: variable d'environnement).
        api_key: Clé API (défaut: variable d'environnement).
        max_retries: Nombre maximum de tentatives (défaut: 3).

    Returns:
        True si l'envoi a réussi, False sinon.
    """
    url     = api_url or API_URL
    key     = api_key or API_KEY
    payload = {
        "bin_id":          bin_id,
        "fill_percentage": round(fill_percentage, 1),
    }
    if distance_cm is not None:
        payload["distance_cm"] = round(distance_cm, 1)

    # Headers d'authentification
    headers = {
        "Content-Type": "application/json",
        "X-API-KEY":    key,
    }

    # Retry avec backoff exponentiel
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Envoi tentative {attempt}/{max_retries} → {url}")
            logger.info(f"  Poubelle #{bin_id} | Remplissage : {fill_percentage:.1f}%")

            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=10,
            )

            if response.ok:
                data = response.json()
                logger.info(f"✅ Envoi réussi : {data.get('message', 'OK')}")
                if data.get('alert_created'):
                    logger.warning("⚠️  ALERTE créée côté serveur (poubelle critique !)")
                log_to_file(bin_id, fill_percentage, "SUCCESS")
                return True
            else:
                logger.error(f"Erreur serveur {response.status_code} : {response.text[:100]}")

        except requests.exceptions.ConnectionError:
            logger.error(f"Connexion impossible vers {url}")
        except requests.exceptions.Timeout:
            logger.error("Délai de connexion dépassé (10s)")
        except requests.exceptions.RequestException as e:
            logger.error(f"Erreur requête : {e}")

        # Attente exponentielle avant la prochaine tentative
        if attempt < max_retries:
            wait = 2 ** (attempt - 1)
            logger.info(f"  Nouvelle tentative dans {wait}s...")
            time.sleep(wait)

    # Toutes les tentatives ont échoué
    logger.error(f"❌ Envoi échoué après {max_retries} tentatives")
    log_to_file(bin_id, fill_percentage, "FAILED")
    return False


if __name__ == "__main__":
    """
    Test de l'envoyeur : envoie une mesure de test au serveur.
    Usage : python send_data.py
    """
    logger.info("=== Test d'envoi SmartWaste ===")
    success = send_fill_level(
        bin_id=BIN_ID,
        fill_percentage=42.5,
        distance_cm=34.5,
    )
    print(f"\nRésultat : {'✅ Succès' if success else '❌ Échec'}")
