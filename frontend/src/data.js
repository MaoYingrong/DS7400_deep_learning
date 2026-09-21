// Loads graph.json (built by pipeline/build_data.py) and prepares lookups for the viewer.
export async function loadGraph() {
  const res = await fetch(`${import.meta.env.BASE_URL}data/graph.json`)
  if (!res.ok) throw new Error(`Could not load data/graph.json (HTTP ${res.status})`)
  const { nodes, edges, disciplines } = await res.json()

  // cites[i]   = ids of the sampled papers that paper i cites
  // citedBy[i] = ids of the sampled papers that cite paper i
  const cites = nodes.map(() => [])
  const citedBy = nodes.map(() => [])
  for (const [from, to] of edges) {
    cites[from].push(to)
    citedBy[to].push(from)
  }
  for (const n of nodes) {
    n.year = Number(n.date.slice(0, 4))
    n.searchText = `${n.title} ${n.authors.map((a) => a.name).join(' ')} ${n.doi}`.toLowerCase()
  }
  return { nodes, edges, disciplines, cites, citedBy }
}
