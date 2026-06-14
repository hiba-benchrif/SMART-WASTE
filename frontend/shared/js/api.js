/**
 * shared/js/api.js — Client API SmartWaste
 *
 * Ce fichier centralise toutes les communications avec le backend Flask.
 * Il fournit des fonctions async pour chaque endpoint de l'API.
 *
 * Gestion des tokens :
 *   - Le token JWT est stocké dans localStorage sous 'sw_token'
 *   - L'objet User est stocké sous 'sw_user' (JSON)
 *   - Toutes les requêtes authentifiées ajoutent automatiquement le header Authorization
 *
 * Gestion des erreurs :
 *   - Toutes les fonctions lèvent une Error avec le message du serveur en cas d'échec
 *   - Le code appelant doit envelopper les appels dans try/catch
 */

// URL de base de l'API backend
// Utilise le chemin relatif /api si l'application est unifiée (comme sur Hugging Face),
// et bascule sur le port 5000 uniquement si le frontend est servi sur le port 8080 ou en protocole file://.
const API_BASE = window.location.port === '8080' || window.location.protocol === 'file:'
  ? 'http://localhost:5000/api'
  : '/api';

// ── Gestion du token et de l'utilisateur ───────────────────────────────────────

/** Récupère le token JWT depuis localStorage */
function getToken() {
  return localStorage.getItem('sw_token') || '';
}

/** Sauvegarde le token JWT dans localStorage */
function setToken(token) {
  localStorage.setItem('sw_token', token);
}

/** Récupère l'objet utilisateur depuis localStorage */
function getUser() {
  try {
    return JSON.parse(localStorage.getItem('sw_user') || 'null');
  } catch {
    return null;
  }
}

/** Sauvegarde l'objet utilisateur dans localStorage */
function setUser(user) {
  localStorage.setItem('sw_user', JSON.stringify(user));
}

/**
 * Déconnecte l'utilisateur et redirige vers la page de connexion.
 * Supprime le token et les données utilisateur du localStorage.
 */
function logout() {
  localStorage.removeItem('sw_token');
  localStorage.removeItem('sw_user');
  // Redirige vers la racine du frontend (la page de connexion)
  const base = window.location.pathname.includes('/admin/')
    || window.location.pathname.includes('/driver/')
    || window.location.pathname.includes('/citizen/')
    ? '../../login.html' : '/login.html';
  window.location.href = base;
}

/**
 * Vérifie si l'utilisateur est connecté et a le bon rôle.
 * Redirige vers login.html si non connecté.
 *
 * @param {string|string[]} requiredRole - Rôle(s) requis pour la page
 */
function requireAuth(requiredRole = null) {
  const user = getUser();
  const token = getToken();

  if (!user || !token) {
    window.location.href = '../login.html';
    return false;
  }

  if (requiredRole) {
    const roles = Array.isArray(requiredRole) ? requiredRole : [requiredRole];
    if (!roles.includes(user.role)) {
      alert(`Accès refusé — Rôle requis : ${roles.join(' ou ')}`);
      window.location.href = '../login.html';
      return false;
    }
  }

  return user;
}

// ── Fonction de requête centrale ───────────────────────────────────────────────

/**
 * Effectue une requête HTTP vers l'API SmartWaste.
 *
 * Ajoute automatiquement :
 * - Content-Type: application/json
 * - Authorization: Bearer <token> si un token existe
 *
 * @param {string} path - Chemin de l'API (ex: '/bins')
 * @param {RequestInit} options - Options fetch (method, body, headers...)
 * @returns {Promise<any>} Données JSON de la réponse
 * @throws {Error} Si la requête échoue (statut non-2xx)
 */
async function apiRequest(path, options = {}) {
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };

  // Ajoute le token JWT si disponible
  const token = getToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  // Tentative de parsing JSON (même en cas d'erreur, le serveur renvoie du JSON)
  let data;
  try {
    data = await response.json();
  } catch {
    data = {};
  }

  if (!response.ok) {
    throw new Error(data.error || data.message || `Erreur HTTP ${response.status}`);
  }

  return data;
}

// ── Authentification ───────────────────────────────────────────────────────────

/**
 * Connecte un utilisateur et sauvegarde son token.
 *
 * @param {string} emailOrUsername - Email ou nom d'utilisateur
 * @param {string} password - Mot de passe en clair
 * @returns {Promise<{access_token: string, user: object}>}
 */
async function login(emailOrUsername, password) {
  const data = await apiRequest('/login', {
    method: 'POST',
    body: JSON.stringify({ email_or_username: emailOrUsername, password }),
  });
  setToken(data.access_token);
  setUser(data.user);
  return data;
}

/**
 * Crée un nouveau compte utilisateur (admin uniquement).
 *
 * @param {object} userData - {username, email, password, role}
 * @returns {Promise<object>} Utilisateur créé
 */
async function register(userData) {
  return apiRequest('/register', { method: 'POST', body: JSON.stringify(userData) });
}

// ── Poubelles ──────────────────────────────────────────────────────────────────

/** Récupère toutes les poubelles actives */
async function getBins() {
  return apiRequest('/bins');
}

/**
 * Récupère les poubelles dans un rayon donné.
 *
 * @param {number} lat - Latitude de l'utilisateur
 * @param {number} lng - Longitude de l'utilisateur
 * @param {number} radius - Rayon en km (défaut: 2)
 * @returns {Promise<Array>} Poubelles triées par distance, avec champ distance_km
 */
async function getNearbyBins(lat, lng, radius = 2) {
  return apiRequest(`/nearby-bins?lat=${lat}&lng=${lng}&radius=${radius}`);
}

/**
 * Marque une poubelle comme collectée (remet fill_percentage à 0).
 * Nécessite un token driver ou admin.
 *
 * @param {number} binId - ID de la poubelle
 */
async function collectBin(binId) {
  return apiRequest(`/collect/${binId}`, { method: 'POST' });
}

/** Crée une nouvelle poubelle (admin) */
async function createBin(data) {
  return apiRequest('/bins', { method: 'POST', body: JSON.stringify(data) });
}

/** Met à jour une poubelle (admin) */
async function updateBin(id, data) {
  return apiRequest(`/bins/${id}`, { method: 'PUT', body: JSON.stringify(data) });
}

/** Désactive une poubelle (admin) */
async function deleteBin(id) {
  return apiRequest(`/bins/${id}`, { method: 'DELETE' });
}

// ── Alertes ────────────────────────────────────────────────────────────────────

/**
 * Récupère les alertes.
 *
 * @param {string} status - 'active', 'resolved', ou 'all'
 * @returns {Promise<Array>}
 */
async function getAlerts(status = 'active') {
  return apiRequest(`/alerts?status=${status}`);
}

/** Résout une alerte */
async function resolveAlert(alertId) {
  return apiRequest(`/alerts/${alertId}/resolve`, { method: 'PATCH' });
}

/** Nombre d'alertes actives */
async function getAlertCount() {
  return apiRequest('/alerts/count');
}

// ── Analytiques ────────────────────────────────────────────────────────────────

/** Statistiques globales du tableau de bord */
async function getStats() {
  return apiRequest('/stats');
}

/**
 * Prédiction ML du temps avant remplissage complet.
 *
 * @param {number} binId - ID de la poubelle
 * @returns {Promise<object>} Résultat de prédiction
 */
async function getPrediction(binId) {
  return apiRequest(`/prediction/${binId}`);
}

/** Détection du pic hebdomadaire */
async function getWeeklyPeak() {
  return apiRequest('/weekly-peak');
}

/**
 * Historique de remplissage pour les graphiques.
 *
 * @param {number|null} binId - ID de la poubelle (null = toutes)
 * @param {number} days - Nombre de jours (défaut: 7)
 */
async function getHistory(binId = null, days = 7) {
  const param = binId ? `&bin_id=${binId}` : '';
  return apiRequest(`/history?days=${days}${param}`);
}

// ── Données de démo ────────────────────────────────────────────────────────────

/** Initialise les données de démonstration */
async function seedData() {
  return apiRequest('/seed', { method: 'POST' });
}

// ── Utilitaires UI ─────────────────────────────────────────────────────────────

/**
 * Affiche une notification toast.
 *
 * @param {string} message - Message à afficher
 * @param {'success'|'error'|'warning'} type - Type de notification
 * @param {number} duration - Durée en ms (défaut: 3000)
 */
function showToast(message, type = 'success', duration = 3500) {
  // Créer ou récupérer le conteneur de toasts
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'toast-container';
    document.body.appendChild(container);
  }

  const icons = { success: 'fa-check-circle', error: 'fa-times-circle', warning: 'fa-exclamation-triangle' };

  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `
    <i class="fas ${icons[type] || icons.success} toast-icon"></i>
    <span class="toast-message">${message}</span>
  `;

  container.appendChild(toast);

  // Suppression automatique après la durée
  setTimeout(() => {
    toast.style.animation = 'fadeIn 0.3s ease reverse';
    setTimeout(() => toast.remove(), 300);
  }, duration);
}

/**
 * Retourne la classe CSS correspondant au statut d'une poubelle.
 *
 * @param {string} status - 'empty', 'medium', ou 'full'
 * @returns {string} Classe CSS
 */
function getStatusClass(status) {
  const map = { empty: 'empty', medium: 'medium', full: 'full' };
  return map[status] || 'empty';
}

/**
 * Retourne le label français d'un statut.
 *
 * @param {string} status - Statut de la poubelle
 * @returns {string} Label en français
 */
function getStatusLabel(status) {
  const map = { empty: 'Disponible', medium: 'Mi-remplie', full: 'Pleine' };
  return map[status] || 'Inconnu';
}

/**
 * Formate une date ISO en format lisible en français.
 *
 * @param {string} isoString - Date au format ISO 8601
 * @returns {string} Date formatée
 */
function formatDate(isoString) {
  if (!isoString) return '—';
  return new Date(isoString).toLocaleString('fr-FR', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit'
  });
}
