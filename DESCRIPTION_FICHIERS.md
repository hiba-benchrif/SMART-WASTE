# SmartWaste Smart City System — Description Complète des Fichiers

> **Ce document explique exhaustivement chaque fichier du projet : pourquoi il existe, ce qu'il fait, comment il fonctionne, et comment il se connecte aux autres fichiers.**

---

## Vue d'ensemble de l'Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   RASPBERRY PI (IoT Layer)                      │
│  HC-SR04 → sensor.py → send_data.py → HTTP POST /api/bin-data  │
└───────────────────────────────┬─────────────────────────────────┘
                                │ X-API-KEY
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                   BACKEND Flask (Port 5000)                     │
│                                                                  │
│  app.py (factory)                                                │
│  ├── routes/auth.py      → /api/login, /api/register, /api/me   │
│  ├── routes/bins.py      → /api/bins, /api/nearby-bins          │
│  ├── routes/sensor.py    → /api/bin-data (reçoit Pi data)       │
│  ├── routes/alerts.py    → /api/alerts                          │
│  ├── routes/analytics.py → /api/stats, /api/prediction, /seed   │
│  ├── models.py           → User, Bin, BinLevel, Alert           │
│  ├── ml/predict.py       → Prédictions ML (fill rate, peak)     │
│  └── utils/geo.py        → Formule Haversine                    │
│                                                                  │
│  PostgreSQL DB ← SQLAlchemy ORM                                 │
└───────────────────────┬─────────────────────────────────────────┘
                        │ REST API (JSON)
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│                   FRONTEND Nginx (Port 8080)                    │
│                                                                  │
│  index.html       → Page d'accueil (landing)                    │
│  login.html       → Connexion JWT                               │
│  citizen/         → Carte + poubelles proches (sans login)      │
│  driver/          → Tournée collecte (login driver/admin)       │
│  admin/           → Dashboard complet (login admin)             │
│                                                                  │
│  shared/css/style.css  → Système de design global               │
│  shared/js/api.js      → Client API (fetch + JWT)               │
│  shared/js/map.js      → Leaflet.js utilitaires                 │
└─────────────────────────────────────────────────────────────────┘
```

## Flux de données complet

```
1. [Pi] HC-SR04 mesure distance
2. [Pi] sensor.py calcule fill_percentage
3. [Pi] send_data.py POST /api/bin-data avec X-API-KEY
4. [Backend] sensor.py route valide la clé (SHA-256)
5. [Backend] Mise à jour Bin.fill_percentage en DB
6. [Backend] Création BinLevel (historique)
7. [Backend] Si fill >= 80% → création Alert
8. [Frontend] Lecture GET /api/bins → affichage carte
9. [Admin] GET /api/stats → tableaux de bord
10. [ML] GET /api/prediction/<id> → heures restantes
```

---

## 📁 Dossier racine

### `docker-compose.yml`

**Pourquoi ce fichier existe :**
Docker Compose orchestre les 3 services (db, backend, frontend) en un seul
fichier déclaratif. Sans lui, il faudrait lancer 3 commandes `docker run`
manuellement avec toutes leurs options de configuration.

**Ce qu'il fait :**
- Définit 3 services : PostgreSQL, Flask/Gunicorn, Nginx
- Configure les dépendances entre services (`depends_on`)
- Déclare un health check sur PostgreSQL pour éviter que Flask démarre
  avant que la base de données soit prête (problème classique)
- Définit un réseau interne `smartwaste_net` pour la communication inter-services
- Crée un volume persistant `postgres_data` pour les données de la DB

**Comment il fonctionne :**
```yaml
depends_on:
  db:
    condition: service_healthy   # ← Flask attend que pg_isready réussisse
```
Le backend ne démarre qu'après que le health check PostgreSQL soit OK.
C'est une protection contre les race conditions au démarrage.

**Connexions :**
- Utilise le fichier `.env` pour les variables d'environnement
- Se base sur les `Dockerfile` dans `backend/` et `frontend/`
- Le réseau permet à Nginx de proxy vers `http://backend:5000`

---

### `.env`

**Pourquoi ce fichier existe :**
Les secrets (mots de passe, clés API, clés JWT) ne doivent **jamais** être
écrits directement dans le code source. Le fichier `.env` les isole dans un
seul fichier exclu du contrôle de version (`.gitignore`).

**Ce qu'il fait :**
Contient toutes les variables secrètes :
- `DATABASE_URL` : chaîne de connexion PostgreSQL
- `JWT_SECRET_KEY` : clé de signature des tokens JWT (à changer en production)
- `PI_API_KEY` : clé brute utilisée par le Raspberry Pi
- `PI_API_KEY_HASH` : hash SHA-256 de la clé Pi stocké côté serveur
- `CORS_ORIGINS` : origines autorisées pour les requêtes cross-origin

**Points importants :**
Le backend compare le hash SHA-256 de la clé reçue avec `PI_API_KEY_HASH`.
La clé brute n'est jamais stockée côté serveur (principe zero-knowledge).

---

## 📁 `backend/`

### `backend/app.py`

**Pourquoi ce fichier existe :**
Point d'entrée principal de l'application Flask. Il utilise le **Factory Pattern**
(fonction `create_app()`) — une bonne pratique Flask qui permet de créer
plusieurs instances de l'app avec des configurations différentes (dev, test, prod)
et évite les imports circulaires.

**Ce qu'il fait :**
1. Instancie Flask
2. Charge la configuration depuis `config.py`
3. Initialise les extensions : SQLAlchemy, JWTManager, Flask-CORS, Flask-Limiter
4. Enregistre les 5 blueprints (groupes de routes)
5. Crée les tables DB au démarrage
6. Configure le logging vers `logs/app.log`

**Comment il fonctionne :**
```python
app = create_app()              # Factory
db.init_app(app)                # Extension liée à l'app
app.register_blueprint(auth_bp) # Routes enregistrées
db.create_all()                 # Tables créées si inexistantes
```

**Connexions :**
- Importe : `config.py`, `models.py`, tous les `routes/`, extensions Flask
- Est importé par : Gunicorn (`gunicorn app:app`)

---

### `backend/config.py`

**Pourquoi ce fichier existe :**
Centralise toute la configuration dans une seule classe Python.
Utiliser `os.getenv()` permet de lire les variables d'environnement du `.env`
sans les écrire en dur dans le code.

**Ce qu'il fait :**
Définit la classe `Config` avec :
- `SQLALCHEMY_DATABASE_URI` : URL de connexion PostgreSQL
- `JWT_SECRET_KEY` + `JWT_ACCESS_TOKEN_EXPIRES` : configuration JWT (8h)
- `PI_API_KEY_HASH` : hash de la clé Pi pour l'authentification capteur
- `CORS_ORIGINS` : liste des origines frontend autorisées
- `RATE_LIMIT` : limite anti-abus (300 req/heure)
- `ML_MODELS_PATH` : chemin vers les modèles ML `.pkl`

**Connexions :**
- Importé par : `app.py` (`app.config.from_object(Config)`)
- Lit depuis : variables d'environnement du `.env`

---

### `backend/models.py`

**Pourquoi ce fichier existe :**
Définit le schéma de la base de données en Python via SQLAlchemy ORM.
Chaque classe Python = une table PostgreSQL. SQLAlchemy génère le SQL
automatiquement, ce qui évite d'écrire des requêtes SQL manuellement.

**Ce qu'il fait — 4 modèles :**

| Modèle | Table | Description |
|--------|-------|-------------|
| `User` | `users` | Comptes admin et chauffeur avec hash de mot de passe |
| `Bin` | `bins` | Poubelles physiques avec GPS et niveau de remplissage |
| `BinLevel` | `bin_levels` | Historique de chaque mesure du capteur |
| `Alert` | `alerts` | Alertes générées quand fill ≥ 80% |

**Comment il fonctionne :**
```python
class User(db.Model):
    password_hash = db.Column(db.String(255))  # Jamais le mot de passe !

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)  # Werkzeug PBKDF2

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
```
Werkzeug utilise PBKDF2-SHA256 avec sel aléatoire — résistant aux attaques
par dictionnaire et arc-en-ciel.

Chaque modèle a une méthode `to_dict()` qui sérialise l'objet en dictionnaire
JSON-compatible pour les réponses API.

**Connexions :**
- Importé par : tous les fichiers `routes/`, `ml/predict.py`
- Dépend de : `flask_sqlalchemy` (SQLAlchemy), `werkzeug.security`

---

### `backend/routes/auth.py`

**Pourquoi ce fichier existe :**
Blueprint Flask dédié à l'authentification. Séparé des autres routes pour
respecter le principe de responsabilité unique (SRP).

**Ce qu'il fait :**
- `POST /api/login` : vérifie les identifiants, crée et retourne un token JWT
- `POST /api/register` : crée un compte (admin requis)
- `GET /api/me` : retourne l'utilisateur connecté
- `GET /api/health` : vérification de santé de l'API

**Comment il fonctionne :**
```
Login :
  1. Cherche l'utilisateur par email OU username
  2. check_password() compare avec Werkzeug
  3. create_access_token(identity=str(user.id)) signe le JWT
  4. Le JWT contient l'ID + le rôle dans ses "claims"
```
Le token est valide 8 heures (configurable via `JWT_EXPIRES_HOURS`).

**Sécurité :**
- Le rôle est dans le token mais également vérifié en DB à chaque requête
- L'enregistrement requiert un token admin (`@roles_required('admin')`)

---

### `backend/routes/bins.py`

**Pourquoi ce fichier existe :**
Gère toutes les opérations CRUD sur les poubelles + la géolocalisation.

**Ce qu'il fait :**
- `GET /api/bins` : liste publique de toutes les poubelles actives
- `GET /api/nearby-bins?lat=&lng=&radius=` : poubelles dans un rayon (Haversine)
- `POST /api/bins` : créer une poubelle (admin)
- `PUT /api/bins/<id>` : modifier (admin)
- `DELETE /api/bins/<id>` : soft delete — is_active=False (admin)
- `POST /api/collect/<id>` : marquer collectée — reset fill à 0% (driver/admin)

**Comment fonctionne le soft delete :**
La poubelle n'est pas supprimée de la DB (`DELETE FROM bins`).
On met juste `is_active = False`. Cela préserve l'historique des mesures
(`BinLevel`) et des alertes liées à cette poubelle.

**Comment fonctionne nearby-bins :**
1. Lit lat, lng, radius depuis les query params
2. Valide les coordonnées (`validate_coordinates`)
3. Charge toutes les poubelles actives depuis la DB
4. Appelle `find_nearby_bins()` de `utils/geo.py` (Haversine)
5. Retourne les poubelles dans le rayon, triées par distance

---

### `backend/routes/sensor.py`

**Pourquoi ce fichier existe :**
Endpoint spécialisé pour la réception des données du Raspberry Pi.
Utilise une authentification par clé API (X-API-KEY) plutôt que JWT,
car le Pi ne peut pas faire une session interactive de connexion.

**Ce qu'il fait :**
- `POST /api/bin-data` : reçoit fill_percentage + distance_cm du Pi
- `GET /api/bin-data/<id>` : historique des mesures (admin/driver)

**Comment fonctionne l'authentification Pi :**
```python
received_hash = hashlib.sha256(key.encode()).hexdigest()
hmac.compare_digest(received_hash, stored_hash)  # Timing-safe
```
`hmac.compare_digest` compare en temps constant pour éviter les attaques
par timing (où la durée de comparaison révèle combien de caractères sont corrects).

**Logique d'alerte automatique :**
```
Si fill >= 80% ET aucune alerte active n'existe pour cette poubelle :
  → Créer un enregistrement Alert avec message descriptif
```
La condition "aucune alerte active" évite les doublons d'alertes.

---

### `backend/routes/alerts.py`

**Pourquoi ce fichier existe :**
Gère les alertes générées automatiquement par le système.

**Ce qu'il fait :**
- `GET /api/alerts?status=active` : liste des alertes (filtrables)
- `GET /api/alerts/count` : compteur pour le badge dans la navigation
- `PATCH /api/alerts/<id>/resolve` : résoudre manuellement une alerte

**Points importants :**
Le compteur `/count` est utilisé par le frontend pour afficher un badge
rouge sans charger toute la liste. C'est une optimisation de performance.

---

### `backend/routes/analytics.py`

**Pourquoi ce fichier existe :**
Routes analytiques avancées : statistiques agrégées, ML, historique et seed.

**Ce qu'il fait :**
- `GET /api/stats` : KPIs du tableau de bord (total bins, alertes, fill moyen)
- `GET /api/prediction/<id>` : délègue à `ml/predict.py`
- `GET /api/weekly-peak` : délègue à `ml/predict.py`
- `GET /api/history?days=7` : données pour les graphiques Chart.js
- `POST /api/seed` : crée les données de démo (idempotent)

**Comment fonctionne le seed (idempotent) :**
```python
if User.query.filter_by(email="admin@smartwaste.local").first():
    return "données déjà créées"   # Ne rien faire si déjà seeded
```
Cette vérification garantit qu'on peut appeler `/seed` plusieurs fois
sans dupliquer les données.

**Comment est généré l'historique simulé :**
Pour chaque poubelle, 100 mesures sont créées sur 7 jours avec une
progression linéaire du remplissage + bruit aléatoire (±2%) pour
simuler un comportement réaliste.

---

### `backend/ml/train_model.py`

**Pourquoi ce fichier existe :**
Entraîne le modèle de régression linéaire sur des données synthétiques.
Les données synthétiques sont nécessaires car on n'a pas encore d'historique
réel (c'est un nouveau système). Une fois en production, on peut ré-entraîner
sur les vraies données.

**Ce qu'il fait :**
1. `generate_synthetic_data()` : simule 20 poubelles sur 60 jours avec
   des patterns réalistes (pics vendredi/samedi, creux la nuit)
2. `train_fill_predictor()` : entraîne un Pipeline sklearn :
   - `StandardScaler` : normalise les features (heure, jour, temps écoulé)
   - `LinearRegression` : modèle de régression linéaire
3. `save_models()` : sauvegarde le `.pkl` avec `joblib`

**Pourquoi LinearRegression :**
- Simple à interpréter (les chauffeurs peuvent comprendre "X% par heure")
- Performant avec peu de données
- Pas de surapprentissage sur des données limitées
- scikit-learn Pipeline facilite la normalisation + prédiction en une étape

**Comment lancer l'entraînement :**
```bash
python backend/ml/train_model.py
```

---

### `backend/ml/predict.py`

**Pourquoi ce fichier existe :**
Charge les modèles ML et fournit les fonctions de prédiction appelées par les routes.

**Ce qu'il fait :**

**`predict_hours_until_full(bin_id)`** :
1. Récupère les 50 dernières mesures BinLevel de la poubelle
2. Calcule la vitesse de remplissage :
   ```
   vitesse = (fill_dernière - fill_première) / heures_écoulées
   ```
3. Calcule les heures restantes :
   ```
   heures = (100 - fill_actuel) / vitesse
   ```
4. Niveau de confiance : high (≥20 mesures) / medium (5-19) / low (<5)

**`detect_weekly_peak()`** :
1. Récupère les BinLevel des 30 derniers jours
2. Groupe par `timestamp.weekday()` (0=Lundi, 6=Dimanche)
3. Calcule le remplissage moyen par jour
4. Retourne le jour avec le max → jour de collecte prioritaire

**Optimisation (cache) :**
```python
_fill_model = None  # Cache global du modèle

def load_fill_predictor():
    global _fill_model
    if _fill_model is not None:
        return _fill_model      # Retourne le cache, pas de rechargement
```
Le fichier `.pkl` n'est chargé qu'une seule fois au premier appel.

---

### `backend/middleware/role_middleware.py`

**Pourquoi ce fichier existe :**
Implémente le contrôle d'accès basé sur les rôles (RBAC — Role Based Access Control).
Centralise la logique d'autorisation pour éviter de la dupliquer dans chaque route.

**Ce qu'il fait :**
Le décorateur `@roles_required('admin', 'driver')` :
1. Appelle `verify_jwt_in_request()` → vérifie le token
2. Extrait l'ID utilisateur avec `get_jwt_identity()`
3. Charge l'utilisateur depuis la DB
4. Vérifie que `user.role in roles`
5. Si non autorisé → 403 Forbidden

**Usage dans les routes :**
```python
@bins_bp.post('/collect/<int:bin_id>')
@roles_required('admin', 'driver')    # ← Ce décorateur
def collect_bin(bin_id):
    ...
```

---

### `backend/utils/geo.py`

**Pourquoi ce fichier existe :**
Implémente la formule de Haversine pour calculer les distances GPS.
C'est un calcul trigonométrique non trivial qui doit être testé et isolé.

**Ce qu'il fait :**
```
Formule de Haversine :
a = sin²(Δlat/2) + cos(lat1) × cos(lat2) × sin²(Δlng/2)
c = 2 × arcsin(√a)
distance = 6371 × c  (rayon de la Terre en km)
```

La formule tient compte de la courbure de la Terre.
Pour Casablanca (33°N), l'approximation plane serait erronée de ~0.1% à 2km.

**`find_nearby_bins()` :**
Itère sur toutes les poubelles, calcule la distance Haversine de chacune,
filtre celles dans le rayon, ajoute `distance_km` dans le dictionnaire,
et retourne la liste triée par distance croissante.

---

### `backend/utils/validators.py`

**Pourquoi ce fichier existe :**
Valider les données entrantes est critique pour la sécurité. Ce fichier centralise
toutes les validations pour éviter la duplication et faciliter les tests.

**Ce qu'il fait :**
- `require_fields()` : vérifie que les champs JSON obligatoires sont présents
- `validate_fill_level()` : vérifie que fill est entre 0 et 100
- `validate_coordinates()` : vérifie lat (-90,90) et lng (-180,180)
- `validate_role()` : vérifie que le rôle est dans VALID_ROLES
- `validate_radius()` : vérifie que le rayon est positif et ≤ max

**Pattern de retour :**
```python
def validate_fill_level(value) -> tuple:
    return (True, float_value)   # Succès
    return (False, "message")    # Erreur
```
Ce pattern `(bool, valeur_ou_erreur)` permet un code propre dans les routes.

---

### `backend/utils/helpers.py`

**Pourquoi ce fichier existe :**
Regroupe des fonctions utilitaires pures (sans accès DB) réutilisées partout.

**Ce qu'il fait :**
- `calculate_status(fill)` : convertit 75% → 'medium'
- `generate_alert_message(bin_name, fill)` : génère le message d'alerte lisible
- `format_prediction_response(...)` : formate le résultat ML en JSON propre

---

### `backend/utils/constants.py`

**Pourquoi ce fichier existe :**
DRY (Don't Repeat Yourself). En centralisant les seuils dans un seul fichier,
on n'a qu'un seul endroit à modifier si les seuils changent.

**Ce qu'il fait :**
Définit : `EMPTY_THRESHOLD=50`, `MEDIUM_THRESHOLD=80`, `ALERT_THRESHOLD=80`,
`DEFAULT_RADIUS_KM=2.0`, `FRENCH_DAYS`, `DEFAULT_FILL_RATE_PER_HOUR=5.0`

---

## 📁 `frontend/`

### `frontend/shared/css/style.css`

**Pourquoi ce fichier existe :**
Un seul fichier CSS centralisé est plus maintenable que des CSS séparés par page.
Le système de design avec variables CSS permet de changer le thème entier
en modifiant quelques variables.

**Ce qu'il fait (1000+ lignes) :**
- Variables CSS (`--primary`, `--shadow-lg`, etc.) : tokens de design
- Reset et base typographique (Inter, tailles, couleurs)
- Composants réutilisables : boutons, cartes, badges, barres de progression,
  toasts, modales, tableaux, formulaires
- Mises en page : landing, login, citizen (carte+panneau), driver, admin (sidebar)
- Animations : fadeIn, slideUp, scaleIn, pulseRed pour les poubelles critiques
- Responsive : breakpoints 1024px, 768px, 480px
- Glassmorphism : `backdrop-filter: blur(20px)` + `rgba` transparent

**Design tokens importants :**
```css
--primary: #059669;         /* Vert emeraude principal */
--status-empty:  #10b981;   /* Vert — poubelle disponible */
--status-medium: #f59e0b;   /* Orange — à surveiller */
--status-full:   #ef4444;   /* Rouge — intervention requise */
```

---

### `frontend/shared/js/api.js`

**Pourquoi ce fichier existe :**
Centralise TOUTE la communication avec le backend. Si l'URL du serveur change,
il n'y a qu'un endroit à modifier (`API_BASE`).

**Ce qu'il fait :**
- Gestion du token JWT dans `localStorage` (`sw_token`, `sw_user`)
- Fonction centrale `apiRequest()` qui ajoute automatiquement `Authorization: Bearer`
- Fonctions pour chaque endpoint : `getBins()`, `login()`, `collectBin()`, etc.
- `requireAuth(role)` : vérifie le token et le rôle, redirige si non autorisé
- `showToast()` : notifications toast avec 3 types (success, error, warning)
- `formatDate()` : formate les dates ISO en français

**Gestion des erreurs :**
```javascript
if (!response.ok) {
    throw new Error(data.error || `Erreur HTTP ${response.status}`);
}
```
Les pages enveloppent les appels dans `try/catch` pour afficher des toasts d'erreur.

---

### `frontend/shared/js/map.js`

**Pourquoi ce fichier existe :**
Leaflet.js est une bibliothèque complexe. Ce fichier fournit une API simplifiée
adaptée à SmartWaste — les pages n'ont pas à connaître les détails de Leaflet.

**Ce qu'il fait :**
- `initMap(elementId, lat, lng, zoom)` : initialise la carte avec tuiles OpenStreetMap
- `createBinMarker(bin, onClick)` : crée un marqueur HTML circulaire coloré selon fill%
- `drawBinsOnMap(bins)` : affiche tous les marqueurs (efface les anciens d'abord)
- `addUserMarker(lat, lng)` : point bleu pulsant pour la position utilisateur
- `showRadiusCircle(lat, lng, km)` : cercle vert translucide pour le rayon de recherche
- `centerMap(lat, lng, zoom)` : animation `flyTo` vers des coordonnées
- `getUserLocation()` : wrapper Promise autour de `navigator.geolocation`

**Marqueurs dynamiques :**
Les marqueurs utilisent `L.divIcon` avec du HTML personnalisé pour afficher
le pourcentage et animer les poubelles critiques (≥80%) avec une pulsation rouge.

---

### `frontend/index.html`

**Pourquoi ce fichier existe :**
Page d'accueil publique qui présente le système et guide les utilisateurs
vers leur interface appropriée (Citoyen, Chauffeur, Admin).

**Ce qu'il fait :**
- Hero section avec titre gradient, sous-titre et boutons d'action
- Section "Lancer la démo" : appelle `POST /api/seed` via `seedData()`
- 3 cartes de rôles avec icônes, descriptions et liens
- Section features : IoT, ML, Géolocalisation, Alertes
- Informations sur les comptes de démonstration

---

### `frontend/login.html`

**Pourquoi ce fichier existe :**
Page de connexion unique pour les admins et chauffeurs.
Le design glassmorphism sur fond sombre crée une interface professionnelle.

**Ce qu'il fait :**
- Formulaire email/username + password avec toggle visibilité
- Appelle `login(identifier, password)` de `api.js`
- Redirige selon le rôle : admin → `admin/index.html`, driver → `driver/index.html`
- Affiche les identifiants de démonstration pour faciliter les tests
- Si déjà connecté (token valide) → redirection automatique

---

### `frontend/citizen/index.html`

**Pourquoi ce fichier existe :**
Interface publique pour les citoyens. Aucun compte requis.
Le citoyen veut juste savoir quelle poubelle est disponible près de lui.

**Ce qu'il fait :**
- Affiche toutes les poubelles sur la carte Leaflet au chargement
- Bouton "Localiser ma position" → `getUserLocation()` → `getNearbyBins(lat, lng)`
- Panneau gauche : poubelle disponible la plus proche (highlight vert)
- Liste des poubelles proches triées par distance avec barres de remplissage
- Filtres : Toutes / Disponibles / Pleines
- Boutons "Ouvrir dans Google Maps" pour la navigation
- Marqueur bleu pour la position utilisateur + cercle de rayon 2km

---

### `frontend/driver/index.html`

**Pourquoi ce fichier existe :**
Interface opérationnelle pour le chauffeur. Affiche les poubelles prioritaires
(≥50%, triées par fill décroissant) et permet de marquer les collectes.

**Ce qu'il fait :**
- Vérification auth (`requireAuth(['driver', 'admin'])`) au chargement
- Panneau gauche : stats (total, critiques), liste des prioritaires avec fill bars
- Bouton "Marquer Collectée" → `collectBin(id)` → reset à 0% + résolution alertes
- Auto-refresh toutes les 60 secondes avec compte à rebours
- Géolocalisation du chauffeur (marqueur bleu)
- Carte avec tous les marqueurs colorés

---

### `frontend/admin/index.html`

**Pourquoi ce fichier existe :**
Dashboard complet de gestion pour les administrateurs.
Centralise toutes les fonctionnalités de supervision du système.

**Ce qu'il fait — 5 sections :**

1. **Tableau de bord** : 4 KPI cards + 3 graphiques Chart.js :
   - Ligne : évolution 7 jours (`GET /api/history`)
   - Barres : pic hebdomadaire (`GET /api/weekly-peak`)
   - Donut : distribution des états (empty/medium/full)

2. **Poubelles** : tableau CRUD avec fill bars, modale d'ajout/édition

3. **Alertes** : liste filtrée (active/résolue) avec boutons résolution

4. **Prédictions ML** : sélection poubelle → résultat de prédiction + graphique pic

5. **Utilisateurs** : création de nouveaux comptes (register admin/driver)

---

## 📁 `raspberry_pi/`

### `raspberry_pi/sensor.py`

**Pourquoi ce fichier existe :**
Contrôle le capteur HC-SR04 via GPIO. Séparé de `send_data.py` pour respecter
le principe de responsabilité unique — le capteur ne connaît pas le réseau.

**Ce qu'il fait :**
- Initialise GPIO en mode BCM (numérotation Broadcom)
- `measure_distance()` : génère l'impulsion TRIG de 10µs et mesure le retour ECHO
- Timeout de 1 seconde avec `time.time()` pour éviter une boucle infinie
- `distance_to_fill_level()` : `fill = 100 - (distance / hauteur) × 100`
- `get_fill_percentage()` : médiane de 3 mesures pour réduire le bruit

**Gestion d'erreur GPIO :**
```python
try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False  # Mode simulation sur non-Pi
```

---

### `raspberry_pi/send_data.py`

**Pourquoi ce fichier existe :**
Responsable uniquement de l'envoi HTTP. Si le protocole de communication change
(ex: MQTT au lieu de HTTP), seul ce fichier est modifié.

**Ce qu'il fait :**
- `send_fill_level()` : POST vers `/api/bin-data` avec header `X-API-KEY`
- Retry exponentiel : 1s, 2s, 4s entre les tentatives
- Journal CSV dans `data_log.txt` : timestamp, bin_id, fill, SUCCESS/FAILED
- Timeout de 10s pour les requêtes HTTP

---

### `raspberry_pi/simulate_pi.py`

**Pourquoi ce fichier existe :**
Permet de tester TOUT le système sans Raspberry Pi physique.
Indispensable pour le développement et les démonstrations.

**Ce qu'il fait :**
- Simule N poubelles (configurable via `NUM_BINS`)
- Chaque poubelle a un niveau initial aléatoire (10-60%)
- Chaque cycle : +0.5 à +5% aléatoire
- Collecte automatique simulée à 95%
- Affichage coloré dans le terminal avec barres ASCII
- Envoi via `send_data.py` toutes les `INTERVAL_SECONDS` secondes
- Fonctionne sur Windows, Linux, macOS (pas de GPIO)

---

## Glossaire Technique

| Terme | Explication |
|-------|-------------|
| **JWT** | JSON Web Token — token d'authentification signé contenant l'identité de l'utilisateur |
| **BCrypt/PBKDF2** | Algorithmes de hachage sécurisé pour les mots de passe (résistants aux GPUs) |
| **SHA-256** | Algorithme de hachage cryptographique utilisé pour la clé API Pi |
| **Haversine** | Formule trigonométrique calculant la distance entre 2 points GPS sur une sphère |
| **HC-SR04** | Capteur ultrason : émet une onde sonore et mesure le temps de retour (écho) |
| **GPIO BCM** | Mode de numérotation des broches du Raspberry Pi (Broadcom SOC Channel) |
| **REST API** | Architecture d'API basée sur HTTP avec des verbes (GET, POST, PUT, DELETE) |
| **Blueprint Flask** | Module de routes Flask permettant de découper l'app en groupes logiques |
| **ORM SQLAlchemy** | Object-Relational Mapper — traduit des classes Python en tables SQL |
| **LinearRegression** | Modèle ML qui ajuste une droite y=ax+b sur des données |
| **Soft Delete** | Désactivation logique d'un enregistrement (is_active=False) sans suppression physique |
| **CORS** | Cross-Origin Resource Sharing — contrôle quels domaines peuvent appeler l'API |
| **RBAC** | Role-Based Access Control — autorisation basée sur les rôles |
| **Glassmorphism** | Technique CSS : fond semi-transparent + flou (backdrop-filter: blur) |
| **Leaflet.js** | Bibliothèque JavaScript open-source pour cartes interactives |
| **Chart.js** | Bibliothèque JavaScript pour graphiques (lignes, barres, donut) |
| **joblib** | Bibliothèque Python pour sérialiser/désérialiser efficacement les modèles sklearn |
| **Gunicorn** | Serveur WSGI Python de production (remplace le serveur de dev Flask) |
| **WSGI** | Web Server Gateway Interface — standard Python pour les apps web |
| **Backoff exponentiel** | Stratégie de retry : attendre 1s, 2s, 4s entre les tentatives |

---

## Décisions de Conception

### Pourquoi Flask et pas Django ?
Flask est plus léger et flexible pour une API REST. Django est plus adapté
aux applications avec des vues HTML complexes. Flask + SQLAlchemy + JWT
est la stack standard pour les APIs REST Python en 2024.

### Pourquoi PostgreSQL et pas SQLite ?
PostgreSQL supporte les transactions ACID, la concurrence, et les données
géospatiales. SQLite n'est pas adapté à un serveur multi-utilisateurs.
En développement, on peut utiliser SQLite en changeant `DATABASE_URL`.

### Pourquoi Linear Regression pour le ML ?
- Interprétable : on peut expliquer "la poubelle se remplit à 5%/h"
- Peu de données : la régression linéaire fonctionne avec peu d'historique
- Rapide : pas de GPU requis, calcul en millisecondes
- Pour la production, on pourrait passer à ARIMA ou LSTM avec plus de données

### Pourquoi la formule Haversine côté serveur ?
- Calcul côté serveur = la logique métier reste centralisée
- Le frontend (api.js) n'a qu'à passer lat/lng
- La DB filtre les résultats avant envoi (pas de chargement de toutes les poubelles côté client)

### Pourquoi stocker le hash SHA-256 de la clé Pi ?
Si le serveur est compromis et que la DB est exposée, l'attaquant ne peut pas
récupérer la clé Pi brute. Il ne peut que voir le hash, qui ne peut pas être
"déchaîné" (SHA-256 est une fonction unidirectionnelle).

### Pourquoi un soft delete pour les poubelles ?
Supprimer physiquement une poubelle supprimerait aussi tout son historique
de mesures (BinLevel) et ses alertes, à cause des clés étrangères.
Le soft delete préserve l'historique pour les analytics et audits.
