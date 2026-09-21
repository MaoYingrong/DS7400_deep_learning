import { useEffect, useMemo, useState } from 'react'
import { loadGraph } from './data'
import { buildColorMap } from './colors'
import GraphMap from './components/GraphMap'
import Sidebar from './components/Sidebar'
import DetailPanel from './components/DetailPanel'

const DEFAULT_FILTERS = { journal: 'all', yearFrom: 2016, yearTo: 2022, minCited: 0, hidden: new Set(), showAllEdges: false }

export default function App() {
  const [graph, setGraph] = useState(null)
  const [error, setError] = useState(null)
  const [selectedId, setSelectedId] = useState(null)
  const [focus, setFocus] = useState(null) // {id} - tells the map to fly to a paper
  const [query, setQuery] = useState('')
  const [filters, setFilters] = useState(DEFAULT_FILTERS)

  useEffect(() => {
    loadGraph().then(setGraph).catch((e) => setError(e.message))
  }, [])

  const colorMap = useMemo(() => (graph ? buildColorMap(graph.disciplines) : {}), [graph])
  const journals = useMemo(() => (graph ? [...new Set(graph.nodes.map((n) => n.abbr))].sort() : []), [graph])
  const years = [2016, 2017, 2018, 2019, 2020, 2021, 2022]

  // visible[i] is true when paper i passes every filter.
  const visible = useMemo(() => {
    if (!graph) return []
    const f = filters
    return graph.nodes.map(
      (n) =>
        !f.hidden.has(n.discipline) && (f.journal === 'all' || n.abbr === f.journal) &&
        n.year >= f.yearFrom && n.year <= f.yearTo && n.cited >= f.minCited,
    )
  }, [graph, filters])
  const shown = useMemo(() => visible.filter(Boolean).length, [visible])

  // Search: every word must appear in the title, an author name, or the DOI.
  const results = useMemo(() => {
    const words = query.toLowerCase().split(/\s+/).filter(Boolean)
    if (!graph || words.length === 0) return []
    return graph.nodes
      .filter((n) => words.every((w) => n.searchText.includes(w)))
      .sort((a, b) => b.cited - a.cited)
      .slice(0, 30)
  }, [graph, query])

  // Select a paper; `fly` also moves the map to it (used for search results and list clicks).
  const select = (id, fly = false) => {
    setSelectedId(id)
    if (fly && id != null) {
      // Make sure the paper isn't hidden by a filter, otherwise there'd be nothing to fly to.
      if (!visible[id]) setFilters(DEFAULT_FILTERS)
      setFocus({ id })
    }
  }

  if (error) return <div className="status error">Failed to load data: {error}<br />Run <code>python pipeline/build_data.py</code> first.</div>
  if (!graph) return <div className="status">Loading papers…</div>

  return (
    <div className="app">
      <header>
        <h1>APS Citation Explorer</h1>
        <span className="muted">
          {graph.nodes.length.toLocaleString()} sampled Physical Review papers (2016–2022) · {graph.edges.length.toLocaleString()} citation links
        </span>
      </header>
      <main>
        <Sidebar
          graph={graph} colorMap={colorMap} query={query} setQuery={setQuery} results={results}
          onSelect={select} filters={filters} setFilters={setFilters} journals={journals} years={years} shown={shown}
        />
        <GraphMap
          graph={graph} visible={visible} colorMap={colorMap} selectedId={selectedId}
          focus={focus} showAllEdges={filters.showAllEdges} onSelect={select}
        />
        <DetailPanel
          key={selectedId} graph={graph} node={selectedId == null ? null : graph.nodes[selectedId]}
          colorMap={colorMap} onSelect={select}
        />
      </main>
    </div>
  )
}
