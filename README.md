---
title: SmartWaste Smart City System
emoji: 🗑️
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# 🗑️ SmartWaste Smart City System

> Système intelligent de gestion des poubelles urbaines — Casablanca, Maroc 🇲🇦  
> IoT (Raspberry Pi) · Machine Learning · Géolocalisation · Alertes temps réel

---

## 📋 Description

SmartWaste est un système complet de gestion intelligente des déchets urbains.
Des capteurs ultrason HC-SR04 connectés à des Raspberry Pi mesurent le niveau
de remplissage des poubelles et envoient les données au serveur cloud toutes les
10 minutes. Un tableau de bord en temps réel permet aux administrateurs et
chauffeurs de gérer les collectes efficacement, tandis que les citoyens peuvent
trouver la poubelle disponible la plus proche de leur position.

### Fonctionnalités principales

| Fonctionnalité | Description |
|---|---|
| 📡 **IoT capteur** | HC-SR04 sur Raspberry Pi → mesure distance → calcul fill% |
| 🚨 **Alertes automatiques** | Notification dès qu'une poubelle dépasse 80% |
| 🤖 **Prédiction ML** | Régression linéaire : heures restantes avant remplissage |
| 📅 **Pic hebdomadaire** | Détection du jour de la semaine le plus chargé |
| 🗺️ **Géolocalisation** | Haversine + Leaflet : poubelles proches triées par distance |
| 🔐 **3 rôles** | Admin (tout), Chauffeur (collecte + alertes), Citoyen (public) |

---

## 🏗️ Architecture

```
┌─────────────────┐    HTTP POST     ┌──────────────────┐    SQL    ┌─────────────┐
│  Raspberry Pi   │  X-API-KEY auth  │   Flask Backend  │◄────────►│ PostgreSQL  │
│  HC-SR04 sensor │ ───────────────► │   Port 5000      │          │   Port 5432 │
│  sensor.py      │                  │   Gunicorn WSGI  │          └─────────────┘
│  send_data.py   │                  └────────┬─────────┘
└─────────────────┘                           │ REST API JSON
                                              ▼
                                   ┌──────────────────────┐
                                   │    Nginx Frontend    │
                                   │      Port 8080       │
                                   │  ┌───────────────┐   │
                                   │  │  index.html   │   │ Landing page
                                   │  │  login.html   │   │ Connexion JWT
                                   │  │  citizen/     │   │ Carte publique
                                   │  │  driver/      │   │ Tournée collecte
                                   │  │  admin/       │   │ Dashboard complet
                                   │  └───────────────┘   │
                                   └──────────────────────┘
```

---

## 🚀 Installation rapide (Docker)

### Prérequis
- [Docker Desktop](https://www.docker.com/products/docker-desktop) ≥ 24.0
- [Docker Compose](https://docs.docker.com/compose/) ≥ 2.0 (inclus dans Docker Desktop)

### Démarrage en 3 commandes

```bash
# 1. Cloner le projet
git clone https://github.com/votre-username/smartwaste.git
cd smartwaste

# 2. Lancer tous les services
docker compose up --build -d

# 3. Initialiser les données de démonstration
curl -X POST http://localhost:5000/api/seed
```

Ouvrir dans le navigateur : **http://localhost:8080**

### Arrêter les services

```bash
docker compose down          # Arrêter (données conservées)
docker compose down -v       # Arrêter + supprimer les données
```

---

## ⚙️ Configuration

### Fichier `.env`

Copier et adapter le fichier `.env` avant le démarrage :

```env
# Base de données
DATABASE_URL=postgresql://smartwaste:smartwaste_password@db:5432/smartwaste

# JWT — CHANGER EN PRODUCTION !
JWT_SECRET_KEY=votre-cle-secrete-tres-longue-et-aleatoire
JWT_EXPIRES_HOURS=8

# Clé API Raspberry Pi
PI_API_KEY=votre-cle-api-raspberry-pi
PI_API_KEY_HASH=hash-sha256-de-la-cle  # python -c "import hashlib; print(hashlib.sha256('votre-cle'.encode()).hexdigest())"

# CORS
CORS_ORIGINS=http://localhost:8080,http://localhost:3000
```

> ⚠️ **IMPORTANT** : Générer une vraie `JWT_SECRET_KEY` en production :
> ```bash
> python -c "import secrets; print(secrets.token_hex(32))"
> ```

---

## 🎭 Données de démonstration

### Initialisation

```bash
# Via curl
curl -X POST http://localhost:5000/api/seed

# Via le navigateur : cliquer sur "Lancer la démo" sur la page d'accueil
```

### Comptes créés

| Rôle | Email | Mot de passe | Interface |
|------|-------|--------------|-----------|
| 👑 Admin | `admin@smartwaste.local` | `admin12345` | http://localhost:8080/admin/ |
| 🚛 Chauffeur | `driver@smartwaste.local` | `driver12345` | http://localhost:8080/driver/ |
| 👥 Citoyen | *(sans compte)* | *(aucun)* | http://localhost:8080/citizen/ |

### Poubelles créées (Casablanca)

| Poubelle | Quartier | Remplissage | Statut |
|----------|----------|-------------|--------|
| Poubelle Maarif 1 | Maarif | 25% | 🟢 Disponible |
| Poubelle Maarif 2 | Maarif | 55% | 🟡 Mi-remplie |
| Poubelle Zerktouni 1 | Maarif | 82% | 🔴 Pleine |
| Poubelle Hassan II 1 | Centre-ville | 91% | 🔴 Pleine |
| Poubelle Corniche 1 | Ain Diab | 45% | 🟢 Disponible |
| Poubelle Hay Mohammadi | Hay Mohammadi | 73% | 🟡 Mi-remplie |
| Poubelle Anfa | Anfa | 38% | 🟢 Disponible |
| Poubelle Sidi Moumen | Sidi Moumen | 67% | 🟡 Mi-remplie |

---

## 📱 Interfaces

### 🏠 Page d'accueil (`/`)
Page de présentation du système avec accès aux 3 espaces.

### 🗺️ Espace Citoyen (`/citizen/`)
- Carte Leaflet plein écran avec toutes les poubelles
- Bouton "Localiser ma position" → geolocation API
- Panneau gauche : poubelle disponible la plus proche
- Liste des poubelles proches triées par distance
- Filtres : Toutes / Disponibles / Pleines
- Boutons Google Maps pour la navigation

### 🚛 Espace Chauffeur (`/driver/`)
- Authentification JWT requise (driver ou admin)
- Panneau : poubelles prioritaires (≥50%) triées par remplissage
- Bouton "Marquer Collectée" → reset à 0% + résolution alertes
- Auto-refresh toutes les 60 secondes
- Géolocalisation du chauffeur sur la carte

### 🖥️ Espace Admin (`/admin/`)
- Authentification JWT requise (admin uniquement)
- **Tableau de bord** : 4 KPI + 3 graphiques Chart.js
- **Poubelles** : tableau CRUD avec fill bars, modal ajout/édition
- **Alertes** : liste filtrée avec résolution manuelle
- **Prédictions ML** : heures restantes + pic hebdomadaire
- **Utilisateurs** : création de comptes chauffeur/admin

---

## 📡 Référence API

### Authentification

| Méthode | Endpoint | Auth | Description |
|---------|----------|------|-------------|
| POST | `/api/login` | — | Connexion, retourne JWT |
| POST | `/api/register` | JWT Admin | Créer un compte |
| GET | `/api/me` | JWT | Utilisateur connecté |
| GET | `/api/health` | — | Statut de l'API |

### Poubelles

| Méthode | Endpoint | Auth | Description |
|---------|----------|------|-------------|
| GET | `/api/bins` | — | Liste toutes les poubelles |
| GET | `/api/nearby-bins?lat=&lng=&radius=2` | — | Poubelles proches (Haversine) |
| POST | `/api/bins` | JWT Admin | Créer une poubelle |
| PUT | `/api/bins/<id>` | JWT Admin | Modifier une poubelle |
| DELETE | `/api/bins/<id>` | JWT Admin | Désactiver (soft delete) |
| POST | `/api/collect/<id>` | JWT Driver/Admin | Marquer collectée |

### Capteur IoT

| Méthode | Endpoint | Auth | Description |
|---------|----------|------|-------------|
| POST | `/api/bin-data` | X-API-KEY | Envoi mesure Pi |
| GET | `/api/bin-data/<id>` | JWT | Historique mesures |

### Analytiques

| Méthode | Endpoint | Auth | Description |
|---------|----------|------|-------------|
| GET | `/api/stats` | JWT Admin | Statistiques globales |
| GET | `/api/prediction/<id>` | JWT Admin/Driver | Prédiction ML |
| GET | `/api/weekly-peak` | JWT Admin | Pic hebdomadaire |
| GET | `/api/history?days=7` | JWT Admin | Historique graphiques |
| POST | `/api/seed` | — | Données de démo |

### Alertes

| Méthode | Endpoint | Auth | Description |
|---------|----------|------|-------------|
| GET | `/api/alerts?status=active` | JWT Admin/Driver | Liste alertes |
| GET | `/api/alerts/count` | JWT Admin/Driver | Nombre d'alertes actives |
| PATCH | `/api/alerts/<id>/resolve` | JWT Admin/Driver | Résoudre une alerte |

---

## 🤖 Machine Learning

### Modèle 1 : Prédiction du remplissage

**Algorithme** : Régression linéaire (scikit-learn Pipeline)

**Features** :
- `hour_of_day` : heure de la journée (0-23)
- `day_of_week` : jour de la semaine (0=Lundi, 6=Dimanche)
- `hours_elapsed` : heures écoulées depuis la première mesure

**Calcul de prédiction** (basé sur l'historique) :
```
fill_speed = (fill_dernière_mesure - fill_première_mesure) / heures_écoulées
hours_until_full = (100 - fill_actuel) / fill_speed
```

**Niveaux de confiance** :
- 🟢 **Élevée** : ≥ 20 mesures disponibles
- 🟡 **Moyenne** : 5 à 19 mesures
- 🔴 **Faible** : < 5 mesures (estimation par défaut : 5%/h)

### Entraînement des modèles

```bash
# Dans le conteneur backend
docker exec smartwaste_backend python ml/train_model.py

# En local
cd backend
python ml/train_model.py
```

Les modèles sont sauvegardés dans `backend/ml/models/fill_predictor.pkl`.
Auto-entraînement au démarrage si le fichier `.pkl` n'existe pas.

---

## 🔌 Configuration Raspberry Pi

### Câblage HC-SR04

```
Raspberry Pi 4          HC-SR04
──────────────          ───────
Pin 2  (5V)    ──────►  VCC
Pin 6  (GND)   ──────►  GND
Pin 16 (GPIO23)──────►  TRIG
Pin 18 (GPIO24)◄──[1kΩ/2kΩ diviseur tension]── ECHO

⚠️  IMPORTANT : Le signal ECHO est en 5V.
    Le GPIO du Pi ne supporte que 3.3V.
    Utiliser un diviseur de tension :
    ECHO ── [1kΩ] ── GPIO24
                  └── [2kΩ] ── GND
```

### Installation sur le Pi

```bash
# Sur le Raspberry Pi
cd raspberry_pi
pip install -r requirements.txt

# Copier et configurer l'environnement
cp .env.example .env
nano .env   # Modifier SMARTWASTE_API_URL et SMARTWASTE_BIN_ID

# Lancer la mesure continue
python sensor.py        # Test du capteur seul
python send_data.py     # Test de l'envoi seul

# Script principal (toutes les 10 minutes)
while true; do
    python -c "
from sensor import get_fill_percentage
from send_data import send_fill_level
import os
fill, dist = get_fill_percentage()
send_fill_level(int(os.getenv('SMARTWASTE_BIN_ID', 1)), fill, dist)
"
    sleep 600
done
```

### Simulation (sans Pi physique)

```bash
# Simule 3 poubelles et envoie les données au serveur
python raspberry_pi/simulate_pi.py

# Configurer le nombre de poubelles et l'intervalle
NUM_BINS=5 INTERVAL_SECONDS=10 python raspberry_pi/simulate_pi.py
```

---

## 💻 Lancement sans Docker (développement)

### Backend Flask

```bash
cd backend

# Créer un environnement virtuel
python -m venv venv
venv\Scripts\activate       # Windows
source venv/bin/activate    # Linux/Mac

# Installer les dépendances
pip install -r requirements.txt

# Configurer la base de données (PostgreSQL requis)
# Modifier DATABASE_URL dans .env pour pointer vers votre PostgreSQL local

# Lancer le serveur de développement
python app.py
# → API disponible sur http://localhost:5000
```

### Frontend

```bash
# Ouvrir directement dans le navigateur
# (pas de serveur requis pour les fichiers HTML statiques)
open frontend/index.html    # Mac
start frontend/index.html   # Windows

# Ou avec un serveur local simple
cd frontend
python -m http.server 8080
# → http://localhost:8080
```

> **Note** : En développement local, le frontend contacte le backend sur
> `http://localhost:5000`. Cette URL est définie dans `shared/js/api.js`.

---

## 🔒 Sécurité

| Mécanisme | Implémentation |
|-----------|----------------|
| Authentification | JWT signé (flask-jwt-extended), expiration 8h |
| Mots de passe | Hash PBKDF2-SHA256 + sel aléatoire (Werkzeug) |
| Clé API Pi | Stockée sous forme SHA-256 (jamais en clair) |
| Comparaison clé | `hmac.compare_digest()` (anti-timing attack) |
| CORS | Flask-CORS avec whitelist d'origines |
| Rate Limiting | Flask-Limiter : 300 req/heure par IP |
| Rôles | Décorateur `@roles_required()` sur chaque route protégée |

---

## 📁 Structure du projet

```
SMART-WASTE/
├── docker-compose.yml          # Orchestration Docker
├── .env                        # Variables d'environnement (secrets)
├── README.md                   # Ce fichier
├── DESCRIPTION_FICHIERS.md     # Description détaillée de chaque fichier
│
├── backend/
│   ├── app.py                  # Factory Flask (point d'entrée)
│   ├── config.py               # Configuration (env vars)
│   ├── models.py               # Modèles DB (User, Bin, BinLevel, Alert)
│   ├── requirements.txt        # Dépendances Python
│   ├── Dockerfile              # Image Docker backend
│   │
│   ├── routes/                 # Endpoints API REST
│   │   ├── auth.py             # Login, register, me
│   │   ├── bins.py             # CRUD poubelles + nearby-bins
│   │   ├── sensor.py           # Réception données Pi
│   │   ├── alerts.py           # Gestion alertes
│   │   └── analytics.py        # Stats, ML, seed
│   │
│   ├── ml/                     # Machine Learning
│   │   ├── train_model.py      # Entraînement (LinearRegression)
│   │   ├── predict.py          # Prédictions (fill rate, peak)
│   │   └── models/             # Modèles sauvegardés (.pkl)
│   │
│   ├── middleware/             # Sécurité
│   │   └── role_middleware.py  # Décorateur @roles_required
│   │
│   ├── utils/                  # Utilitaires
│   │   ├── constants.py        # Constantes globales
│   │   ├── helpers.py          # Fonctions partagées
│   │   ├── validators.py       # Validation des entrées
│   │   └── geo.py              # Formule Haversine
│   │
│   └── logs/                   # Logs applicatifs (créé au runtime)
│
├── frontend/
│   ├── index.html              # Page d'accueil (landing)
│   ├── login.html              # Page de connexion
│   ├── Dockerfile              # Image Docker Nginx
│   ├── nginx.conf              # Config Nginx + proxy API
│   │
│   ├── citizen/
│   │   └── index.html          # Interface citoyen (carte publique)
│   ├── driver/
│   │   └── index.html          # Interface chauffeur
│   ├── admin/
│   │   └── index.html          # Dashboard administrateur
│   │
│   └── shared/
│       ├── css/style.css       # Système de design global
│       └── js/
│           ├── api.js          # Client API + gestion JWT
│           └── map.js          # Utilitaires Leaflet.js
│
└── raspberry_pi/
    ├── sensor.py               # Contrôle HC-SR04 (GPIO)
    ├── send_data.py            # Envoi HTTP avec retry
    ├── simulate_pi.py          # Simulateur (sans Pi physique)
    ├── .env.example            # Template de configuration Pi
    └── requirements.txt        # Dépendances Pi
```

---

## 🛠️ Développement

### Ajouter un nouveau type de capteur

1. Créer un nouveau script dans `raspberry_pi/` (ex: `sensor_v2.py`)
2. Implémenter la fonction `get_fill_percentage()` → `(fill, distance)`
3. Utiliser `send_data.py` pour l'envoi (inchangé)

### Ajouter un nouvel endpoint API

1. Choisir le blueprint approprié dans `backend/routes/`
2. Définir la route avec `@blueprint.get/post/put/delete`
3. Appliquer `@roles_required(...)` si authentification requise
4. Documenter avec une docstring

### Changer le modèle ML

1. Modifier `ml/train_model.py` (remplacer LinearRegression par votre modèle)
2. Mettre à jour `ml/predict.py` (adapter les features si nécessaire)
3. Re-lancer l'entraînement : `python ml/train_model.py`
4. Redémarrer le backend : `docker compose restart backend`

---

## 📊 Monitoring

### Logs du backend

```bash
# Logs en temps réel
docker logs -f smartwaste_backend

# Fichier de log complet
cat backend/logs/app.log

# Journal des envois Raspberry Pi
cat raspberry_pi/data_log.txt
```

### Santé de l'API

```bash
curl http://localhost:5000/api/health
# → {"status": "ok", "message": "SmartWaste API opérationnelle ✅"}
```

---

## 👥 Équipe et Contexte

- **Projet** : PFE (Projet de Fin d'Études)
- **Ville** : Casablanca, Maroc 🇲🇦
- **Technologies** : Python · Flask · PostgreSQL · scikit-learn · Leaflet.js · Docker

---

*SmartWaste — Pour une ville plus propre et plus intelligente* 🌿
