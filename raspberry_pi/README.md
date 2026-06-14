# Raspberry Pi - SmartWaste

Ce dossier contient la partie IoT du projet SmartWaste.

Le Raspberry Pi 4 lit le capteur ultrason HC-SR04, calcule le pourcentage de remplissage de la poubelle, puis envoie la mesure au backend Flask avec une requete HTTP securisee par une cle API.

## Fichiers

- `sensor.py`: script reel pour Raspberry Pi + HC-SR04.
- `simulate_pi.py`: simulation sans capteur physique, utile pour tester la demo.
- `.env.example`: modele de configuration a copier vers `.env`.
- `smartwaste-pi.service`: exemple de service Linux pour lancer le capteur automatiquement au demarrage.
- `requirements.txt`: dependances Python de la partie IoT.
- `requirements-sim.txt`: dependances minimales pour tester la simulation sur PC Windows.

## Branchement HC-SR04

Important: le pin Echo du HC-SR04 sort du 5V. Le Raspberry Pi accepte du 3.3V sur ses GPIO. Il faut utiliser un diviseur de tension pour proteger le Raspberry Pi.

| HC-SR04 | Raspberry Pi |
| --- | --- |
| VCC | 5V |
| GND | GND |
| TRIG | GPIO 23 |
| ECHO | GPIO 24 via diviseur de tension |

Exemple de diviseur de tension pour Echo:

- Echo HC-SR04 -> resistance 1k -> GPIO 24
- GPIO 24 -> resistance 2k -> GND

## Installation sur Raspberry Pi

```bash
cd raspberry_pi
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Configuration

Remplace `YOUR_PC_IP` par l'adresse IP de l'ordinateur qui lance Docker.

```bash
cp .env.example .env
nano .env
```

Exemple de contenu:

```bash
export SMARTWASTE_API_URL="http://YOUR_PC_IP:5000/api/pi/ingest"
export SMARTWASTE_PI_API_KEY="dev-pi-key"
export SMARTWASTE_BIN_ID="1"
export BIN_HEIGHT_CM="60"
export TRIG_PIN="23"
export ECHO_PIN="24"
```

La cle `dev-pi-key` correspond au hash configure dans le fichier `.env` du backend pour le mode developpement.

Si tu utilises le fichier `.env`, tu peux charger les variables avant de lancer le script:

```bash
set -a
source .env
set +a
```

## Lancer le vrai capteur

```bash
python sensor.py
```

Le script envoie une mesure toutes les 10 secondes.

## Tester sans Raspberry Pi

Depuis ton PC, pendant que Docker est lance:

```bash
cd raspberry_pi
pip install -r requirements-sim.txt
python simulate_pi.py
```

Ce script envoie de fausses valeurs au backend. Tu peux ensuite regarder la carte et le dashboard admin.

## Lancer automatiquement au demarrage

Sur le Raspberry Pi, si le projet est dans `/home/pi/SMART-WASTE`, copie le service:

```bash
sudo cp smartwaste-pi.service /etc/systemd/system/smartwaste-pi.service
sudo systemctl daemon-reload
sudo systemctl enable smartwaste-pi
sudo systemctl start smartwaste-pi
```

Voir l'etat du service:

```bash
sudo systemctl status smartwaste-pi
```

Voir les logs:

```bash
journalctl -u smartwaste-pi -f
```

Si ton projet est dans un autre dossier ou si ton utilisateur n'est pas `pi`, modifie `smartwaste-pi.service`.

## Test rapide de connexion

Depuis le Raspberry Pi, teste que le backend est accessible:

```bash
curl http://YOUR_PC_IP:5000/api/health
```

Tester l'envoi d'une mesure:

```bash
curl -X POST http://YOUR_PC_IP:5000/api/pi/ingest \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: dev-pi-key" \
  -d '{"bin_id": 1, "fill_level": 50}'
```

## Comment ca marche

1. Le HC-SR04 envoie une onde ultrason.
2. L'onde rebondit sur les dechets dans la poubelle.
3. Le Raspberry Pi mesure le temps entre l'envoi et le retour.
4. Le script transforme ce temps en distance.
5. Plus la distance est petite, plus la poubelle est pleine.
6. Le script envoie `{ "bin_id": 1, "fill_level": 75 }` au backend Flask.
7. Flask verifie `X-API-KEY`, enregistre la mesure dans PostgreSQL et cree une alerte si la poubelle est presque pleine.

## Securite IoT

- La requete contient l'en-tete `X-API-KEY`.
- Le backend ne stocke pas la cle en clair, il stocke son hash SHA-256.
- En production, il faut utiliser HTTPS ou un reseau prive securise.
- La cle de developpement doit etre remplacee avant un vrai deploiement.
