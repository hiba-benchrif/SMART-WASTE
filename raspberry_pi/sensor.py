"""
raspberry_pi/sensor.py — Lecture du capteur ultrason HC-SR04

Ce script est exécuté directement sur le Raspberry Pi.
Il contrôle le capteur HC-SR04 via les broches GPIO pour mesurer
la distance entre le capteur et le niveau de déchets dans la poubelle.

Principe du HC-SR04 :
  1. Envoyer une impulsion de 10µs sur la broche TRIG
  2. Mesurer la durée de l'impulsion haute sur la broche ECHO
  3. distance_cm = (durée × 34300) / 2  (vitesse du son : 343 m/s)
  4. fill_percentage = 100 - (distance / hauteur_poubelle × 100)

Câblage HC-SR04 → Raspberry Pi (mode BCM) :
  VCC  → 5V    (broche physique 2)
  GND  → GND   (broche physique 6)
  TRIG → GPIO23 (broche physique 16)
  ECHO → GPIO24 (broche physique 18) [via diviseur de tension 1kΩ/2kΩ]

⚠️ IMPORTANT : Le ECHO sort 5V mais le GPIO du Pi ne supporte que 3.3V.
   Utiliser un diviseur de tension ou un convertisseur de niveau logique.
"""

import time
import os
import sys
import logging

# Configuration depuis les variables d'environnement (fichier .env.example)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv optionnel

# Importer la fonction d'envoi de données
sys.path.insert(0, os.path.dirname(__file__))
try:
    from send_data import send_fill_level
except ImportError:
    from raspberry_pi.send_data import send_fill_level

# ── Constantes de configuration ────────────────────────────────────────────────
# Broches GPIO en mode BCM (Broadcom SOC Channel)
TRIG_PIN = int(os.getenv("TRIG_PIN", "23"))
ECHO_PIN = int(os.getenv("ECHO_PIN", "24"))

# Hauteur physique de la poubelle en cm
BIN_HEIGHT_CM = float(os.getenv("BIN_HEIGHT_CM", "60"))

# Paramètres de transmission et identification
BIN_ID = int(os.getenv("SMARTWASTE_BIN_ID", "1"))
INTERVAL_SECONDS = int(os.getenv("INTERVAL_SECONDS", "600"))
API_URL = os.getenv("SMARTWASTE_API_URL", "http://localhost:5000/api/bin-data")
API_KEY = os.getenv("SMARTWASTE_PI_API_KEY", "dev-pi-secret-key-2024")

# Durée maximale d'attente pour le signal ECHO (évite une boucle infinie)
TIMEOUT_SEC = 1.0

# ── Configuration du logger ────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Initialisation GPIO ────────────────────────────────────────────────────────
try:
    import RPi.GPIO as GPIO
    GPIO.setmode(GPIO.BCM)    # Mode de numérotation Broadcom
    GPIO.setwarnings(False)   # Désactiver les avertissements de réutilisation
    GPIO.setup(TRIG_PIN, GPIO.OUT)   # TRIG : sortie (envoie l'impulsion)
    GPIO.setup(ECHO_PIN, GPIO.IN)    # ECHO : entrée (reçoit le rebond)
    GPIO.output(TRIG_PIN, False)     # État initial : bas
    time.sleep(0.1)                  # Attendre la stabilisation du capteur
    logger.info(f"GPIO initialisé — TRIG: GPIO{TRIG_PIN}, ECHO: GPIO{ECHO_PIN}")
    GPIO_AVAILABLE = True

except (ImportError, RuntimeError) as e:
    # Sur Windows/Linux non-Pi : le module RPi.GPIO n'est pas disponible
    logger.warning(f"RPi.GPIO non disponible ({e}). Mode simulation activé.")
    GPIO_AVAILABLE = False


def measure_distance() -> float:
    """
    Mesure la distance en cm entre le capteur HC-SR04 et la surface des déchets.

    Algorithme :
      1. Envoyer une impulsion TRIG de 10 microsecondes
      2. Attendre que ECHO passe à HIGH (début de la réception du son)
      3. Mesurer le temps jusqu'à ce que ECHO repasse à LOW (fin de réception)
      4. distance = (temps_echo × vitesse_son) / 2

    Un timeout de TIMEOUT_SEC évite une boucle infinie si le capteur ne répond pas.

    Returns:
        Distance en centimètres (float), arrondie à 2 décimales.

    Raises:
        RuntimeError: Si GPIO n'est pas disponible ou si le capteur ne répond pas.
    """
    if not GPIO_AVAILABLE:
        raise RuntimeError("GPIO non disponible — utilisez simulate_pi.py pour les tests")

    # Étape 1 : Envoyer l'impulsion TRIG (10 microsecondes)
    GPIO.output(TRIG_PIN, True)
    time.sleep(0.00001)  # 10 µs
    GPIO.output(TRIG_PIN, False)

    # Étape 2 : Attendre que ECHO passe à HIGH
    start_wait = time.time()
    pulse_start = time.time()
    while GPIO.input(ECHO_PIN) == 0:
        pulse_start = time.time()
        if pulse_start - start_wait > TIMEOUT_SEC:
            raise RuntimeError("Timeout : ECHO ne passe pas à HIGH (vérifier le câblage)")

    # Étape 3 : Attendre que ECHO repasse à LOW
    pulse_end = time.time()
    while GPIO.input(ECHO_PIN) == 1:
        pulse_end = time.time()
        if pulse_end - pulse_start > TIMEOUT_SEC:
            raise RuntimeError("Timeout : ECHO reste à HIGH (capteur bloqué ?)")

    # Étape 4 : Calculer la distance
    # Durée de l'impulsion ECHO en secondes
    pulse_duration = pulse_end - pulse_start
    # distance = (durée × vitesse_son_cm_s) / 2 (aller-retour)
    distance_cm = (pulse_duration * 34300) / 2

    return round(distance_cm, 2)


def distance_to_fill_level(distance_cm: float, bin_height_cm: float = BIN_HEIGHT_CM) -> float:
    """
    Convertit une distance mesurée en pourcentage de remplissage.

    Logique :
      - Si distance = bin_height_cm → poubelle vide (0%)
      - Si distance = 0 cm         → poubelle pleine (100%)
      - Formule : fill = 100 - (distance / bin_height) × 100

    Args:
        distance_cm: Distance mesurée par le capteur HC-SR04 (cm).
        bin_height_cm: Hauteur interne de la poubelle (cm).

    Returns:
        Pourcentage de remplissage entre 0.0 et 100.0.
    """
    if bin_height_cm <= 0:
        return 0.0

    # Limiter la distance entre 0 et la hauteur de la poubelle
    distance_cm = max(0, min(distance_cm, bin_height_cm))

    fill_percentage = 100.0 - (distance_cm / bin_height_cm * 100.0)
    return round(fill_percentage, 1)


def get_fill_percentage() -> tuple:
    """
    Effectue une mesure complète et retourne le niveau de remplissage.

    Effectue 3 mesures consécutives et retourne la médiane pour
    réduire les erreurs de mesure (bruit du capteur).

    Returns:
        Tuple (fill_percentage: float, distance_cm: float)

    Raises:
        RuntimeError: Si les 3 mesures échouent.
    """
    distances = []

    for i in range(3):
        try:
            dist = measure_distance()
            # Ignorer les mesures aberrantes (< 2cm ou > 400cm)
            if 2 <= dist <= 400:
                distances.append(dist)
            time.sleep(0.06)  # Pause entre les mesures (recommandation HC-SR04)
        except RuntimeError as e:
            logger.warning(f"Mesure {i+1}/3 échouée : {e}")

    if not distances:
        raise RuntimeError("Toutes les mesures ont échoué — vérifier le capteur")

    # Médiane pour réduire l'impact des valeurs aberrantes
    distances.sort()
    median_dist = distances[len(distances) // 2]

    fill = distance_to_fill_level(median_dist)
    logger.info(f"Distance : {median_dist} cm → Remplissage : {fill}%")

    return fill, median_dist


def cleanup():
    """
    Libère les ressources GPIO proprement.
    Doit être appelé avant de quitter le programme.
    """
    if GPIO_AVAILABLE:
        GPIO.cleanup()
        logger.info("GPIO libéré proprement")


if __name__ == "__main__":
    """
    Exécution principale du capteur : mesure et envoie au serveur en boucle.
    Usage : python sensor.py
    """
    logger.info("=== Démarrage du capteur HC-SR04 ===")
    logger.info(f"ID Poubelle : {BIN_ID}")
    logger.info(f"Hauteur poubelle : {BIN_HEIGHT_CM} cm")
    logger.info(f"Intervalle de mesure : {INTERVAL_SECONDS} secondes")
    logger.info(f"URL de l'API : {API_URL}")
    logger.info("Appuyez sur Ctrl+C pour arrêter\n")

    try:
        while True:
            try:
                fill, dist = get_fill_percentage()
                status = "🟢 Vide" if fill < 50 else "🟡 Mi-remplie" if fill < 80 else "🔴 PLEINE"
                logger.info(f"📏 Mesure: {dist:.1f} cm | Remplissage: {fill:.1f}% | {status}")
                
                # Envoi au serveur Flask (qui tourne sur le PC portable principal)
                success = send_fill_level(
                    bin_id=BIN_ID,
                    fill_percentage=fill,
                    distance_cm=dist,
                    api_url=API_URL,
                    api_key=API_KEY
                )
                if success:
                    logger.info("✅ Transmission réussie")
                else:
                    logger.warning("⚠️ Échec de la transmission (données stockées localement)")
                    
            except RuntimeError as e:
                logger.error(f"Erreur capteur : {e}")

            time.sleep(INTERVAL_SECONDS)

    except KeyboardInterrupt:
        logger.info("\nArrêt du capteur")
    finally:
        cleanup()
