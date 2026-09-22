// Thin wrappers around the backend's REST API (backend/app/main.py).
const path = (doi) => doi.split('/').map(encodeURIComponent).join('/') // DOIs contain "/"

async function check(res) {
  if (!res.ok) throw new Error(`Backend error (HTTP ${res.status})`)
  return res
}

/** DOIs of every hidden paper. */
export const fetchHidden = () =>
  fetch('/api/hidden').then(check).then((r) => r.json()).then((rows) => rows.map((row) => row.doi))

export const hidePaperApi = (doi) => fetch(`/api/hidden/${path(doi)}`, { method: 'PUT' }).then(check)
export const restorePaperApi = (doi) => fetch(`/api/hidden/${path(doi)}`, { method: 'DELETE' }).then(check)
export const restoreAllApi = () => fetch('/api/hidden', { method: 'DELETE' }).then(check)
