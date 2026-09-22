import { useCallback, useEffect, useMemo, useState } from 'react'
import { loadGraph } from './data'
import { fetchAnnotations, putAnnotation } from './api'
import { buildColorMap } from './colors'
import GraphMap from './components/GraphMap'
import Sidebar from './components/Sidebar'
import DetailPanel from './components/DetailPanel'

const DEFAULT_FILTERS = { journal: 'all', yearFrom: 2016, yearTo: 2022, minCited: 0, hidden: new Set(), showAllEdges: false, tag: 'all' }

// Annotation filter: 'all' papers, only 'annotated' ones, or papers carrying one specific tag.
function tagMatches(tag, annotation) {
  if (tag === 'all') return true
  if (tag === 'annotated') return !!annotation
  return !!annotation && annotation.tags.includes(tag)
}

export default function App() {
  const [graph, setGraph] = useState(null)
  const [error, setError] = useState(null)
  const [selectedId, setSelectedId] = useState(null)
  const [focus, setFocus] = useState(null) // {id} - tells the map to fly to a paper
  const [query, setQuery] = useState('')
  const [filters, setFilters] = useState(DEFAULT_FILTERS)
  const [annotations, setAnnotations] = useState({}) // doi -> { tags, note }, mirrored from the backend database
  const [backendOnline, setBackendOnline] = useState(null) // null = still checking

  useEffect(() => {
    loadGraph().then(setGraph).catch((e) => setError(e.message))
    fetchAnnotations()
      .then((a) => { setAnnotations(a); setBackendOnline(true) })
      .catch(() => setBackendOnline(false))
  }, [])

  // Save to the backend, then mirror the stored result locally (an empty annotation means "deleted").
  const saveAnnotation = useCallback(async (doi, value) => {
    const saved = await putAnnotation(doi, value)
    setAnnotations((prev) => {
      const next = { ...prev }
      if (saved.tags.length === 0 && !saved.note) delete next[doi]
      else next[doi] = { tags: saved.tags, note: saved.note }
      return next
    })
  }, [])

  const annotatedIds = useMemo(() => (graph ? graph.nodes.filter((n) => annotations[n.doi]).map((n) => n.id) : []), [graph, annotations])
  const tagCounts = useMemo(() => {
    const counts = {}
    for (const a of Object.values(annotations)) for (const t of a.tags) counts[t] = (counts[t] || 0) + 1
    return counts
  }, [annotations])

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
        n.year >= f.yearFrom && n.year <= f.yearTo && n.cited >= f.minCited && tagMatches(f.tag, annotations[n.doi]),
    )
  }, [graph, filters, annotations])
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
        <span className={`backend-pill ${backendOnline === false ? 'off' : backendOnline ? 'on' : ''}`}>
          {backendOnline === null ? 'Checking backend…' : backendOnline ? `Backend connected · ${annotatedIds.length} annotated` : 'Backend offline'}
        </span>
      </header>
      <main>
        <Sidebar
          graph={graph} colorMap={colorMap} query={query} setQuery={setQuery} results={results}
          onSelect={select} filters={filters} setFilters={setFilters} journals={journals} years={years} shown={shown}
          annotations={annotations} tagCounts={tagCounts} backendOnline={backendOnline}
        />
        <GraphMap
          graph={graph} visible={visible} colorMap={colorMap} selectedId={selectedId}
          focus={focus} showAllEdges={filters.showAllEdges} annotatedIds={annotatedIds} onSelect={select}
        />
        <DetailPanel
          key={selectedId} graph={graph} node={selectedId == null ? null : graph.nodes[selectedId]}
          colorMap={colorMap} onSelect={select}
          annotation={selectedId == null ? null : annotations[graph.nodes[selectedId].doi]}
          onSaveAnnotation={saveAnnotation} backendOnline={backendOnline === true}
        />
      </main>
    </div>
  )
}
