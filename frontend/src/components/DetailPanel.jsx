import { useState } from 'react'
import { fetchPrediction } from '../api'

/** Ask the backend's neural network for this paper's field; show probabilities next to the recorded label. */
function PredictBox({ doi, backendOnline, modelVersion }) {
  const [res, setRes] = useState(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)
  const [forVersion, setForVersion] = useState(modelVersion)
  const run = () => {
    setBusy(true); setErr(null)
    fetchPrediction(doi).then((r) => { setRes(r); setForVersion(modelVersion) }).catch((e) => setErr(e.message)).finally(() => setBusy(false))
  }
  return (
    <section className="predict-box">
      <h3>Neural-network prediction</h3>
      <button className="primary" disabled={!backendOnline || busy} onClick={run}>{busy ? 'Predicting…' : res ? 'Predict again' : 'Predict field'}</button>
      {!backendOnline && <span className="muted small"> Needs the backend.</span>}
      {err && <p className="small" style={{ color: '#b3261e' }}>{err}</p>}
      {res && (
        <div>
          {forVersion !== modelVersion && <p className="small muted">The model changed since this prediction — predict again.</p>}
          <p className="pred-main">Predicted: <b>{res.predicted}</b> ({(res.confidence * 100).toFixed(0)}%)<br />
            <span className={res.correct ? 'ok' : 'bad'}>{res.correct ? '✓ matches' : '✗ differs from'} the recorded field ({res.true})</span><br />
            <span className="muted small">This paper was in the model's <b>{res.split}</b> set{res.split === 'train' ? ' (seen during training)' : ' (unseen during training)'}.</span></p>
          {res.top.map((t) => (
            <div className="bar-row" key={t.label}><span className="bar-label">{t.label}</span><span className="bar"><i style={{ width: `${t.prob * 100}%` }} /></span><span className="bar-pct">{(t.prob * 100).toFixed(0)}%</span></div>
          ))}
        </div>
      )}
    </section>
  )
}

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
export default function DetailPanel({ graph, node, colorMap, onSelect, hiddenDois, onHide, backendOnline, modelVersion }) {
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

      <PredictBox doi={node.doi} backendOnline={backendOnline} modelVersion={modelVersion} />

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
