let smartMap;
let markers = [];

function setupMap() {
  if (!document.getElementById("map")) return;
  smartMap = L.map("map").setView([33.5899, -7.6039], 12);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { attribution: "OpenStreetMap" }).addTo(smartMap);
}

function markerColor(status) {
  if (status === "Full") return "#d64545";
  if (status === "Medium") return "#d89a1d";
  return "#1f9d63";
}

function drawBins(bins) {
  if (!smartMap) return;
  markers.forEach(marker => marker.remove());
  markers = bins.map(bin => {
    const marker = L.circleMarker([bin.latitude, bin.longitude], { radius:10, color:markerColor(bin.status), fillColor:markerColor(bin.status), fillOpacity:.8 }).addTo(smartMap);
    marker.bindPopup(`<strong>${bin.street || "Rue non definie"}</strong><br>${bin.name}<br>${bin.zone || "Zone non definie"}<br>${bin.fill_level}% - ${bin.status}`);
    return marker;
  });
}
