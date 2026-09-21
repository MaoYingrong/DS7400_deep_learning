/** Left column: search box, filters, and the discipline legend (which is also a filter). */
export default function Sidebar({
  graph, colorMap, query, setQuery, results, onSelect, filters, setFilters, journals, years, shown,
}) {
  const set = (patch) => setFilters({ ...filters, ...patch })

  // Legend rows: every discipline that has its own color, plus one row for all the rest.
  const counts = {}
  for (const n of graph.nodes) counts[n.discipline] = (counts[n.discipline] || 0) + 1
  const colored = graph.disciplines.filter((d, i) => i < 7)
  const others = graph.disciplines.filter((d, i) => i >= 7)
  const otherCount = others.reduce((s, d) => s + counts[d], 0)

  const toggle = (names) => {
    const hidden = new Set(filters.hidden)
    const allHidden = names.every((d) => hidden.has(d))
    names.forEach((d) => (allHidden ? hidden.delete(d) : hidden.add(d)))
    set({ hidden })
  }
  const isOn = (names) => names.some((d) => !filters.hidden.has(d))

  return (
    <aside className="sidebar">
      <section>
        <h2>Search</h2>
        <input
          type="search" placeholder="Title, author, or DOI…" value={query}
          onChange={(e) => setQuery(e.target.value)} aria-label="Search papers"
        />
        {query.trim() && (
          <ul className="results">
            {results.length === 0 && <li className="muted">No matching papers</li>}
            {results.map((n) => (
              <li key={n.id}>
                <button onClick={() => onSelect(n.id, true)}>
                  <span className="r-title">{n.title}</span>
                  <span className="r-meta">{n.authors[0]?.name}{n.authors.length > 1 ? ' et al.' : ''} · {n.abbr} {n.year}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h2>Filters</h2>
        <label className="field">Journal
          <select value={filters.journal} onChange={(e) => set({ journal: e.target.value })}>
            <option value="all">All journals</option>
            {journals.map((j) => <option key={j} value={j}>{j}</option>)}
          </select>
        </label>
        <div className="field-row">
          <label className="field">From
            <select value={filters.yearFrom} onChange={(e) => set({ yearFrom: +e.target.value })}>
              {years.map((y) => <option key={y}>{y}</option>)}
            </select>
          </label>
          <label className="field">To
            <select value={filters.yearTo} onChange={(e) => set({ yearTo: +e.target.value })}>
              {years.map((y) => <option key={y}>{y}</option>)}
            </select>
          </label>
        </div>
        <label className="field">Min. citations: <b>{filters.minCited}</b>
          <input type="range" min="0" max="200" step="5" value={filters.minCited} onChange={(e) => set({ minCited: +e.target.value })} />
        </label>
        <label className="check">
          <input type="checkbox" checked={filters.showAllEdges} onChange={(e) => set({ showAllEdges: e.target.checked })} />
          Show all citation links
        </label>
      </section>

      <section>
        <h2>Discipline <span className="muted">({shown} papers shown)</span></h2>
        <ul className="legend">
          {colored.map((d) => (
            <li key={d}>
              <label>
                <input type="checkbox" checked={isOn([d])} onChange={() => toggle([d])} />
                <i style={{ background: colorMap[d] }} />
                <span>{d}</span><span className="muted">{counts[d]}</span>
              </label>
            </li>
          ))}
          {others.length > 0 && (
            <li>
              <label title={others.join(', ')}>
                <input type="checkbox" checked={isOn(others)} onChange={() => toggle(others)} />
                <i style={{ background: colorMap[others[0]] }} />
                <span>Other ({others.length} fields)</span><span className="muted">{otherCount}</span>
              </label>
            </li>
          )}
        </ul>
      </section>
    </aside>
  )
}
