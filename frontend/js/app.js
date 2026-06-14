function binCard(bin) {
  const type = bin.status.toLowerCase();
  return `<article class="item ${type}">
    <strong>${bin.street || "Rue non definie"}</strong>
    <span>${bin.name} - ${bin.fill_level}% - ${bin.status}</span><br>
    <small>${bin.zone || "Zone non definie"} - ${bin.latitude}, ${bin.longitude}</small>
  </article>`;
}

function sortBinsByStreet(bins) {
  return [...bins].sort((a, b) => (a.street || "").localeCompare(b.street || ""));
}

async function loadPublicBins() {
  const bins = await apiRequest("/bins");
  drawBins(bins);
  const list = document.getElementById("binList");
  if (list) list.innerHTML = sortBinsByStreet(bins).map(binCard).join("");
  return bins;
}

function nearestAvailableBin(bins) {
  const available = bins.filter(bin => bin.status !== "Full");
  return available.sort((a, b) => a.fill_level - b.fill_level)[0];
}

async function initCitizen() {
  const bins = await loadPublicBins();
  const button = document.getElementById("nearestBtn");
  if (button) button.addEventListener("click", () => {
    const nearest = nearestAvailableBin(bins);
    document.getElementById("nearestResult").textContent = nearest
      ? `${nearest.street} - ${nearest.name} disponible (${nearest.fill_level}%).`
      : "Aucune poubelle disponible.";
  });
}

function attachLoginForm() {
  const form = document.getElementById("loginForm");
  if (!form) return;
  form.addEventListener("submit", async event => {
    event.preventDefault();
    const data = new FormData(form);
    try {
      const user = await login(data.get("email"), data.get("password"));
      alert(`Connecte comme ${user.role}`);
    } catch (error) {
      alert(error.message);
    }
  });
}

async function initDriver() {
  attachLoginForm();
  await loadPublicBins();
  const button = document.getElementById("routeBtn");
  if (button) button.addEventListener("click", async () => {
    const route = await apiRequest("/driver/route");
    drawBins(route);
    document.getElementById("routeList").innerHTML = sortBinsByStreet(route).map(binCard).join("");
  });
}

async function initAdmin() {
  attachLoginForm();
  await loadPublicBins();
  const seedBtn = document.getElementById("seedBtn");
  if (seedBtn) seedBtn.addEventListener("click", async () => {
    await apiRequest("/seed", { method: "POST" });
    location.reload();
  });
  const statsBtn = document.getElementById("statsBtn");
  if (statsBtn) statsBtn.addEventListener("click", loadStats);
}

async function loadStats() {
  const stats = await apiRequest("/analytics/stats");
  document.getElementById("totalBins").textContent = stats.total_bins;
  document.getElementById("fullBins").textContent = stats.full_bins;
  document.getElementById("avgFill").textContent = `${stats.average_fill_level}%`;
  document.getElementById("alertsList").innerHTML = stats.active_alerts.map(alert => `<article class="item full"><strong>${alert.bin_name}</strong>${alert.message}<br><small>${alert.created_at}</small></article>`).join("");

  const history = await apiRequest("/analytics/history");
  const ctx = document.getElementById("fillChart");
  if (ctx && window.Chart) {
    new Chart(ctx, {
      type: "line",
      data: {
        labels: history.map(item => new Date(item.created_at).toLocaleTimeString()),
        datasets: [{ label: "Fill level", data: history.map(item => item.fill_level), borderColor: "#1f9d63" }],
      },
    });
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const page = location.pathname.split("/").pop();
  
  // Only setup map for citizen/admin pages, driver has its own inline map
  if (page !== "driver.html") {
    setupMap();
  }
  
  if (page === "citizen.html") initCitizen();
  if (page === "driver.html") initDriver();
  if (page === "admin.html") initAdmin();
});
