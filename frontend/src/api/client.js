export async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || response.statusText);
  }
  return response.json();
}

export async function postJson(url, body = {}) {
  return fetchJson(url, {
    method: "POST",
    body: JSON.stringify(body),
  });
}
