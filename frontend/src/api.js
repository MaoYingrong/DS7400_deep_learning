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

// ---- neural network (backend/app/ml.py) ----
const json = (r) => r.json()
const post = (url, body) =>
  fetch(url, { method: 'POST', headers: { 'content-type': 'application/json' }, body: body ? JSON.stringify(body) : undefined }).then(async (res) => {
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || `Backend error (HTTP ${res.status})`)
    return res
  })

export const fetchModel = () => fetch('/api/model').then(check).then(json)
export const fetchPrediction = (doi) => fetch(`/api/predict/${path(doi)}`).then(check).then(json)
export const fetchPredictions = () => fetch('/api/predictions').then(check).then(json)
export const startTraining = (hparams) => post('/api/train', hparams).then(json)
export const stopTraining = () => post('/api/train/stop')
export const fetchTrainStatus = () => fetch('/api/train/status').then(check).then(json)
export const resetModel = () => post('/api/model/reset').then(json)
