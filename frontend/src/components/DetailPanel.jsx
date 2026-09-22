import { useState } from 'react'

function PaperList({ title, ids, nodes, hiddenDois, onSelect }) {
  const shown = ids.filter((i) => !hiddenDois.has(nodes[i].doi)) // hidden papers stay out of the lists too
  const sorted = shown.sort((a, b) => nodes[b].cited - nodes[a].cited)
  const nHidden = ids.length - shown.length
  return (
    <section>
      <h3>{title} <span className="muted">({shown.length} in sample{nHidden ? ` · ${nHidden} hidden` : ''})</span></h3>
      {sorted.length === 0 ? <p className="muted">None in this sample.</p> : (
        <ul className="paper-list">
          {sorted.map((i) => (
            <li key={i}>
              <button onClick={() => onSelect(i, true)}>
                <span className="r-title">{nodes[i].title}</span>
                <span className="r-meta">{nodes[i].abbr} {nodes[i].year} · cited {nodes[i].cited}×</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

/** Right column: everything we know about the selected paper, with clickable neighbours. */
export default function DetailPanel({ graph, node, colorMap, onSelect, hiddenDois, onHide, backendOnline }) {
  const [allAuthors, setAllAuthors] = useState(false)
  if (!node) {
    return (
      <aside className="detail empty">
        <h2>Paper details</h2>
        <p>Click a dot on the map, or search for a paper, to see its details here.</p>
        <p className="muted">Each dot is one APS paper (2016–2022). Dot size = times cited by APS papers; color = discipline; nearby dots share topics and citation neighbours.</p>
      </aside>
    )
  }
  const authors = allAuthors ? node.authors : node.authors.slice(0, 8)
  const affiliations = [...new Set(node.authors.flatMap((a) => a.aff))]
  const byFacet = {}
  for (const c of node.concepts) (byFacet[c.facet || 'Other'] ||= []).push(c)

  return (
    <aside className="detail">
      <h2 className="paper-title">{node.title}</h2>
      <p className="authors">
        {authors.map((a) => a.name).join(', ')}
        {node.authors.length > 8 && (
          <button className="link" onClick={() => setAllAuthors(!allAuthors)}>
            {allAuthors ? ' show fewer' : ` … +${node.authors.length - 8} more`}
          </button>
        )}
      </p>
      <dl className="meta">
        <dt>Journal</dt><dd>{node.journal}{node.volume ? `, vol. ${node.volume}` : ''}{node.issue ? `, issue ${node.issue}` : ''}{node.page ? `, ${node.page}` : ''}</dd>
        <dt>Published</dt><dd>{node.date}{node.type ? ` · ${node.type}` : ''}</dd>
        <dt>DOI</dt><dd><a href={`https://doi.org/${node.doi}`} target="_blank" rel="noreferrer">{node.doi}</a></dd>
        <dt>Cited by</dt><dd>{node.cited} APS papers (2016–2022)</dd>
        <dt>Discipline</dt><dd><i className="swatch" style={{ background: colorMap[node.discipline] }} />{node.disciplines.join('; ')}</dd>
      </dl>

      <div className="hide-box">
        <button className="hide-btn" disabled={!backendOnline} onClick={() => onHide(node.id)}>Hide this paper</button>
        <span className="muted small">
          {backendOnline ? 'Removes it from the map and lists. Restore it any time from “Hidden papers”.' : 'Needs the backend to remember hidden papers (see README).'}
        </span>
      </div>

      {node.concepts.length > 0 && (
        <section>
          <h3>PhySH topics</h3>
          {Object.entries(byFacet).map(([facet, cs]) => (
            <p key={facet} className="facet">
              <span className="muted">{facet}: </span>
              {cs.map((c) => <span key={c.label} className={c.primary ? 'tag primary' : 'tag'}>{c.label}</span>)}
            </p>
          ))}
        </section>
      )}

      {affiliations.length > 0 && (
        <details>
          <summary>Affiliations ({affiliations.length})</summary>
          <ul className="plain">{affiliations.map((a) => <li key={a}>{a}</li>)}</ul>
        </details>
      )}

      <PaperList title="References" ids={graph.cites[node.id]} nodes={graph.nodes} hiddenDois={hiddenDois} onSelect={onSelect} />
      <PaperList title="Cited by" ids={graph.citedBy[node.id]} nodes={graph.nodes} hiddenDois={hiddenDois} onSelect={onSelect} />
    </aside>
  )
}
