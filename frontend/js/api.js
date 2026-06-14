const API_BASE = "http://localhost:5000/api";
let accessToken = localStorage.getItem("smartwaste_token") || "";

async function apiRequest(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || "API error");
  return data;
}

async function login(email, password) {
  const result = await apiRequest("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) });
  accessToken = result.access_token;
  localStorage.setItem("smartwaste_token", accessToken);
  return result.user;
}
