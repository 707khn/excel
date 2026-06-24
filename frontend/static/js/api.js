const API_BASE = "";

export async function apiFetch(path, options = {}) {
  const token = localStorage.getItem("access_token");
  const headers = { ...(options.headers || {}) };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (options.body && typeof options.body === "object" && !(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(options.body);
  }
  let res = await fetch(API_BASE + path, { ...options, headers });
  if (res.status === 401) {
    const refreshed = await _tryRefresh();
    if (refreshed) {
      headers["Authorization"] = `Bearer ${localStorage.getItem("access_token")}`;
      res = await fetch(API_BASE + path, { ...options, headers });
    }
    if (res.status === 401) {
      clearTokens();
      window.location.href = "/";
      return res;
    }
  }
  return res;
}

async function _tryRefresh() {
  const rt = localStorage.getItem("refresh_token");
  if (!rt) return false;
  try {
    const res = await fetch(API_BASE + "/auth/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: rt }),
    });
    if (!res.ok) return false;
    const data = await res.json();
    localStorage.setItem("access_token", data.access_token);
    localStorage.setItem("refresh_token", data.refresh_token);
    return true;
  } catch {
    return false;
  }
}

export function clearTokens() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
  localStorage.removeItem("current_user");
}

export function requireAuth() {
  if (!localStorage.getItem("access_token")) {
    window.location.href = "/";
    return false;
  }
  return true;
}

export function getCurrentUser() {
  const u = localStorage.getItem("current_user");
  return u ? JSON.parse(u) : null;
}
