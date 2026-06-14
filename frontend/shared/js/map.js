/**
 * shared/js/map.js — Utilitaires Leaflet pour SmartWaste
 *
 * Ce fichier gère toutes les interactions avec la carte Leaflet.js :
 * - Initialisation de la carte centrée sur Casablanca
 * - Création de marqueurs colorés selon le niveau de remplissage
 * - Affichage de la position de l'utilisateur (point bleu)
 * - Cercle de rayon de recherche (2km)
 * - Popups d'information sur les poubelles
 *
 * Dépendances :
 *   - Leaflet.js 1.9.4 (chargé via CDN dans le HTML)
 *   - api.js (pour les fonctions utilitaires)
 */

// Instance globale de la carte Leaflet
let smartMap = null;

// Tableau des marqueurs actuellement affichés (pour pouvoir les supprimer)
let binMarkers = [];

// Marqueur de position de l'utilisateur
let userMarker = null;

// Cercle de rayon de recherche
let searchCircle = null;

// ── Initialisation de la carte ──────────────────────────────────────────────

/**
 * Initialise la carte Leaflet dans l'élément HTML spécifié.
 *
 * Centrée sur Casablanca (33.5731°N, 7.5898°O) par défaut.
 * Utilise les tuiles OpenStreetMap (gratuit et open-source).
 *
 * @param {string} elementId - ID de l'élément HTML qui contiendra la carte
 * @param {number} lat - Latitude initiale (défaut: Casablanca)
 * @param {number} lng - Longitude initiale (défaut: Casablanca)
 * @param {number} zoom - Niveau de zoom initial (défaut: 12)
 * @returns {L.Map} Instance de la carte Leaflet
 */
function initMap(elementId = 'map', lat = 33.5731, lng = -7.5898, zoom = 12) {
  // Éviter la double initialisation
  if (smartMap) {
    smartMap.remove();
    smartMap = null;
  }

  // Création de la carte Leaflet
  smartMap = L.map(elementId, {
    zoomControl: true,
    attributionControl: true,
  }).setView([lat, lng], zoom);

  // Couche de tuiles OpenStreetMap
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© <a href="https://openstreetmap.org">OpenStreetMap</a> contributors',
    maxZoom: 19,
  }).addTo(smartMap);

  return smartMap;
}

// ── Couleurs selon le niveau de remplissage ─────────────────────────────────

/**
 * Retourne la couleur hex correspondant au niveau de remplissage.
 *
 * - 0-49%  → Vert  (#10b981) : poubelle disponible
 * - 50-79% → Orange (#f59e0b) : poubelle à mi-capacité
 * - 80-100%→ Rouge  (#ef4444) : poubelle à collecter
 *
 * @param {number} fill - Niveau de remplissage (0-100)
 * @returns {string} Code couleur hexadécimal
 */
function getFillColor(fill) {
  if (fill < 50) return '#10b981';  // Vert — disponible
  if (fill < 80) return '#f59e0b';  // Orange — à surveiller
  return '#ef4444';                  // Rouge — intervention requise
}

// ── Création des marqueurs ──────────────────────────────────────────────────

/**
 * Crée un marqueur circulaire personnalisé pour une poubelle.
 *
 * Le marqueur affiche le pourcentage de remplissage.
 * Les poubelles critiques (≥80%) ont une animation de pulsation.
 * Utilise L.divIcon pour un HTML personnalisé.
 *
 * @param {object} bin - Objet poubelle avec fill_percentage, latitude, longitude
 * @param {Function|null} onClick - Callback appelé lors du clic sur le marqueur
 * @returns {L.Marker} Marqueur Leaflet prêt à être ajouté à la carte
 */
function createBinMarker(bin, onClick = null) {
  const color = getFillColor(bin.fill_percentage);
  const isCritical = bin.fill_percentage >= 80;
  const fill = Math.round(bin.fill_percentage);

  // HTML du marqueur personnalisé
  const markerHtml = `
    <div class="bin-marker ${isCritical ? 'critical' : ''}" 
         style="
           width: 38px; height: 38px;
           background: ${color};
           border: 3px solid white;
           border-radius: 50%;
           display: flex;
           align-items: center;
           justify-content: center;
           font-weight: 800;
           font-size: 11px;
           color: white;
           box-shadow: 0 3px 12px rgba(0,0,0,0.35), 0 0 0 2px ${color}33;
           cursor: pointer;
           font-family: 'Inter', sans-serif;
           transition: transform 0.2s ease;
           ${isCritical ? 'animation: markerPulse 2s infinite;' : ''}
         ">
      ${fill}%
    </div>
  `;

  // Injection du CSS d'animation si pas encore fait
  if (!document.getElementById('marker-styles')) {
    const style = document.createElement('style');
    style.id = 'marker-styles';
    style.textContent = `
      @keyframes markerPulse {
        0%, 100% { box-shadow: 0 3px 12px rgba(239,68,68,0.4), 0 0 0 0 rgba(239,68,68,0.4); }
        50%       { box-shadow: 0 3px 12px rgba(239,68,68,0.4), 0 0 0 8px rgba(239,68,68,0); }
      }
      .bin-marker:hover { transform: scale(1.15) !important; }
      .leaflet-div-icon { background: transparent !important; border: none !important; }
    `;
    document.head.appendChild(style);
  }

  // Création de l'icône Leaflet avec HTML personnalisé
  const icon = L.divIcon({
    html: markerHtml,
    iconSize: [38, 38],
    iconAnchor: [19, 19],
    className: '',
  });

  const marker = L.marker([bin.latitude, bin.longitude], { icon });

  // Contenu du popup au clic sur le marqueur
  const googleMapsUrl = `https://maps.google.com/?q=${bin.latitude},${bin.longitude}`;
  const statusLabel = bin.fill_percentage < 50 ? 'Disponible' : bin.fill_percentage < 80 ? 'Mi-remplie' : '⚠️ Pleine';
  const statusColor = getFillColor(bin.fill_percentage);

  marker.bindPopup(`
    <div style="font-family:'Inter',sans-serif; min-width:200px; padding:4px;">
      <div style="font-weight:700; font-size:15px; margin-bottom:6px; color:#111827;">
        🗑️ ${bin.name}
      </div>
      <div style="font-size:12px; color:#6b7280; margin-bottom:10px;">
        📍 ${bin.address || 'Adresse non définie'}
      </div>
      <div style="
        display:flex; align-items:center; gap:8px;
        background:#f9fafb; border-radius:8px; padding:8px 10px; margin-bottom:10px;
      ">
        <div style="
          width:10px; height:10px; border-radius:50%;
          background:${statusColor}; flex-shrink:0;
        "></div>
        <span style="font-weight:700; color:${statusColor}; font-size:14px;">
          ${bin.fill_percentage}%
        </span>
        <span style="color:#6b7280; font-size:12px;">— ${statusLabel}</span>
      </div>
      ${bin.distance_km !== undefined ? `
        <div style="font-size:12px; color:#6b7280; margin-bottom:10px;">
          📏 Distance : <strong>${bin.distance_km} km</strong>
        </div>
      ` : ''}
      <a href="${googleMapsUrl}" target="_blank" rel="noopener"
         style="
           display:inline-flex; align-items:center; gap:6px;
           background:#059669; color:white; padding:7px 14px;
           border-radius:8px; font-size:13px; font-weight:600;
           text-decoration:none; width:100%; justify-content:center;
         ">
        <i class="fas fa-map-marker-alt"></i> Ouvrir dans Google Maps
      </a>
    </div>
  `, { maxWidth: 260 });

  // Callback de clic personnalisé (optionnel)
  if (onClick) {
    marker.on('click', () => onClick(bin));
  }

  return marker;
}

// ── Affichage des marqueurs ─────────────────────────────────────────────────

/**
 * Dessine tous les marqueurs de poubelles sur la carte.
 * Supprime les anciens marqueurs avant d'en ajouter de nouveaux.
 *
 * @param {Array} bins - Liste d'objets poubelles
 * @param {Function|null} onMarkerClick - Callback de clic
 */
function drawBinsOnMap(bins, onMarkerClick = null) {
  if (!smartMap) return;

  // Suppression des anciens marqueurs
  clearMarkers();

  // Ajout des nouveaux marqueurs
  bins.forEach(bin => {
    const marker = createBinMarker(bin, onMarkerClick);
    marker.addTo(smartMap);
    binMarkers.push(marker);
  });
}

/**
 * Supprime tous les marqueurs de poubelles de la carte.
 */
function clearMarkers() {
  binMarkers.forEach(m => m.remove());
  binMarkers = [];
}

// ── Marqueur utilisateur ────────────────────────────────────────────────────

/**
 * Ajoute ou met à jour le marqueur de position de l'utilisateur (point bleu).
 *
 * @param {number} lat - Latitude de l'utilisateur
 * @param {number} lng - Longitude de l'utilisateur
 */
function addUserMarker(lat, lng) {
  // Suppression du marqueur précédent
  if (userMarker) {
    userMarker.remove();
  }

  // Icône bleue pulsante pour l'utilisateur
  const userIcon = L.divIcon({
    html: `
      <div style="
        width:16px; height:16px;
        background:#3b82f6;
        border: 3px solid white;
        border-radius:50%;
        box-shadow: 0 0 0 6px rgba(59,130,246,0.2), 0 2px 8px rgba(0,0,0,0.3);
        animation: userPulse 2s infinite;
      "></div>
      <style>
        @keyframes userPulse {
          0%, 100% { box-shadow: 0 0 0 6px rgba(59,130,246,0.2); }
          50%       { box-shadow: 0 0 0 10px rgba(59,130,246,0.05); }
        }
      </style>
    `,
    iconSize: [16, 16],
    iconAnchor: [8, 8],
    className: '',
  });

  userMarker = L.marker([lat, lng], { icon: userIcon, zIndexOffset: 1000 })
    .addTo(smartMap)
    .bindPopup('<strong>📍 Votre position</strong>');
}

// ── Cercle de rayon ─────────────────────────────────────────────────────────

/**
 * Affiche un cercle translucide représentant le rayon de recherche.
 *
 * @param {number} lat - Latitude du centre
 * @param {number} lng - Longitude du centre
 * @param {number} radiusKm - Rayon en km (converti en mètres pour Leaflet)
 */
function showRadiusCircle(lat, lng, radiusKm = 2) {
  // Suppression du cercle précédent
  if (searchCircle) {
    searchCircle.remove();
  }

  searchCircle = L.circle([lat, lng], {
    radius: radiusKm * 1000,   // Leaflet attend des mètres
    color: '#059669',
    fillColor: '#059669',
    fillOpacity: 0.06,
    weight: 1.5,
    dashArray: '6 4',
  }).addTo(smartMap);
}

// ── Navigation ──────────────────────────────────────────────────────────────

/**
 * Déplace et zoom la carte vers des coordonnées données.
 *
 * @param {number} lat - Latitude cible
 * @param {number} lng - Longitude cible
 * @param {number} zoom - Niveau de zoom (défaut: 15)
 */
function centerMap(lat, lng, zoom = 15) {
  if (!smartMap) return;
  smartMap.flyTo([lat, lng], zoom, { duration: 1.2 });
}

// ── Géolocalisation ─────────────────────────────────────────────────────────

/**
 * Obtient la position GPS actuelle de l'utilisateur via l'API Geolocation.
 *
 * @returns {Promise<{lat: number, lng: number}>} Position de l'utilisateur
 * @throws {Error} Si la géolocalisation n'est pas supportée ou refusée
 */
function getUserLocation() {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error('La géolocalisation n\'est pas supportée par ce navigateur'));
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (position) => resolve({
        lat: position.coords.latitude,
        lng: position.coords.longitude,
      }),
      (error) => {
        const messages = {
          1: 'Permission de géolocalisation refusée',
          2: 'Position indisponible',
          3: 'Délai de géolocalisation dépassé',
        };
        reject(new Error(messages[error.code] || 'Erreur de géolocalisation'));
      },
      { timeout: 10000, maximumAge: 30000 }
    );
  });
}
