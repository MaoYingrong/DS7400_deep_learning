// Thin wrappers around the backend's REST API (backend/app/main.py).
const path = (doi) => doi.split('/').map(encodeURIComponent).join('/') // DOIs contain "/"

async function json(res) {
  if (!res.ok) throw new Error(`Backend error (HTTP ${res.status})`)
  return res.status === 204 ? null : res.json()
}

/** All saved annotations -> { [doi]: { tags: [...], note: '...' } } */
export async function fetchAnnotations() {
  const list = await fetch('/api/annotations').then(json)
  return Object.fromEntries(list.map((a) => [a.doi, { tags: a.tags, note: a.note }]))
}

/** Create/replace a paper's annotation. No tags and no note deletes it. */
export const putAnnotation = (doi, { tags, note }) =>
  fetch(`/api/annotations/${path(doi)}`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ tags, note }),
  }).then(json)
