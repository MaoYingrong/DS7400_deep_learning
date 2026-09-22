import { useEffect, useMemo, useRef, useState } from 'react'
import { DeckGL, OrthographicView, LinearInterpolator, ScatterplotLayer, LineLayer } from 'deck.gl'
import { hexToRgb, CITES_COLOR, CITED_BY_COLOR } from '../colors'

const VIEW = new OrthographicView({ id: 'map', flipY: false })
const radius = (n) => 1.5 + 0.6 * Math.log2(1 + n.cited) // node size grows with citation count

/** View (center + zoom) that fits every node inside a container of the given pixel size. */
function fitView(nodes, width, height) {
  const xs = nodes.map((n) => n.x), ys = nodes.map((n) => n.y)
  const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)]
  const zoom = Math.log2(Math.min(width / ((x1 - x0) * 1.08), height / ((y1 - y0) * 1.08)))
  return { target: [(x0 + x1) / 2, (y0 + y1) / 2, 0], zoom }
}

/**
 * The map: one dot per paper, positioned by the UMAP layout from the pipeline.
 * Pan = drag, zoom = scroll. Click a dot to select it; its citations are drawn as lines.
 */
export default function GraphMap({ graph, visible, colorMap, selectedId, focus, showAllEdges, onSelect }) {
  const wrapRef = useRef(null)
  const [viewState, setViewState] = useState({ target: [0, 0, 0], zoom: 1.5, minZoom: -1, maxZoom: 8 })
  const [hoverId, setHoverId] = useState(null)
  const tipRef = useRef(null)
  const { nodes, edges, cites, citedBy } = graph

  // Keep the tooltip next to the mouse (moved directly in the DOM so hovering doesn't re-render the map),
  // flipping it to the other side of the cursor near the right / bottom edge.
  const moveTip = (e) => {
    const tip = tipRef.current
    if (!tip) return
    const r = wrapRef.current.getBoundingClientRect()
    const mx = e.clientX - r.left, my = e.clientY - r.top
    const w = tip.offsetWidth || 340, h = tip.offsetHeight || 110
    const x = mx + 14 + w > r.width ? mx - w - 14 : mx + 14
    const y = my + 14 + h > r.height ? my - h - 14 : my + 14
    tip.style.transform = `translate(${Math.max(0, x)}px, ${Math.max(0, y)}px)`
  }

  const resetView = () => {
    const r = wrapRef.current.getBoundingClientRect()
    setViewState((v) => ({
      ...v, ...fitView(nodes, r.width, r.height),
      transitionDuration: 500, transitionInterpolator: new LinearInterpolator(['target', 'zoom']),
    }))
  }

  // Fit the whole map once the container has a size.
  useEffect(() => {
    const r = wrapRef.current.getBoundingClientRect()
    setViewState((v) => ({ ...v, ...fitView(nodes, r.width, r.height) }))
  }, [nodes])

  // Fly to a paper when the sidebar / detail panel asks for it.
  useEffect(() => {
    if (!focus) return
    const n = nodes[focus.id]
    setViewState((v) => ({
      ...v, target: [n.x, n.y, 0], zoom: Math.max(v.zoom, 3),
      transitionDuration: 600, transitionInterpolator: new LinearInterpolator(['target', 'zoom']),
    }))
  }, [focus, nodes])

  const hoverNode = hoverId != null && visible[hoverId] ? nodes[hoverId] : null
  const visibleNodes = useMemo(() => nodes.filter((n) => visible[n.id]), [nodes, visible])

  // The selected paper's neighbours (papers it cites + papers citing it) among the visible ones.
  const related = useMemo(() => {
    if (selectedId == null) return null
    return new Set([...cites[selectedId], ...citedBy[selectedId]].filter((i) => visible[i]))
  }, [selectedId, cites, citedBy, visible])

  const allEdges = useMemo(
    () => (showAllEdges ? edges.filter(([a, b]) => visible[a] && visible[b]) : []),
    [showAllEdges, edges, visible],
  )

  const egoEdges = useMemo(() => {
    if (selectedId == null) return []
    const out = []
    for (const t of cites[selectedId]) if (visible[t]) out.push({ from: selectedId, to: t, color: CITES_COLOR })
    for (const s of citedBy[selectedId]) if (visible[s]) out.push({ from: s, to: selectedId, color: CITED_BY_COLOR })
    return out
  }, [selectedId, cites, citedBy, visible])

  const rgb = useMemo(() => Object.fromEntries(Object.entries(colorMap).map(([k, v]) => [k, hexToRgb(v)])), [colorMap])
  const pos = (i) => [nodes[i].x, nodes[i].y]

  const layers = [
    new LineLayer({
      id: 'all-edges', data: allEdges, getSourcePosition: (e) => pos(e[0]), getTargetPosition: (e) => pos(e[1]),
      getColor: [110, 110, 105, 30], getWidth: 1, widthUnits: 'pixels',
      updateTriggers: { getSourcePosition: allEdges, getTargetPosition: allEdges },
    }),
    new LineLayer({
      id: 'ego-edges', data: egoEdges, getSourcePosition: (e) => pos(e.from), getTargetPosition: (e) => pos(e.to),
      getColor: (e) => [...hexToRgb(e.color), 190], getWidth: 1.5, widthUnits: 'pixels',
    }),
    new ScatterplotLayer({
      id: 'nodes', data: visibleNodes, pickable: true, radiusUnits: 'pixels',
      getPosition: (n) => [n.x, n.y], getRadius: radius,
      getFillColor: (n) => {
        const dim = related && n.id !== selectedId && !related.has(n.id)
        return [...rgb[n.discipline], dim ? 40 : 220]
      },
      updateTriggers: { getFillColor: [selectedId, related, rgb] },
      onHover: (info) => setHoverId(info.object ? info.object.id : null),
    }),
    new ScatterplotLayer({
      id: 'rings', data: [selectedId, hoverId].filter((i) => i != null && visible[i]).map((i) => nodes[i]),
      radiusUnits: 'pixels', stroked: true, filled: false, lineWidthUnits: 'pixels',
      getPosition: (n) => [n.x, n.y], getRadius: (n) => radius(n) + 3,
      getLineWidth: (n) => (n.id === selectedId ? 2.5 : 1.5), getLineColor: [11, 11, 11, 255],
    }),
  ]

  return (
    <div className="map" ref={wrapRef} onMouseMove={moveTip}>
      <DeckGL
        views={VIEW} viewState={viewState} controller
        onViewStateChange={({ viewState: v }) => setViewState(v)}
        layers={layers}
        onClick={(info) => onSelect(info.object ? info.object.id : null)}
        getCursor={({ isHovering }) => (isHovering ? 'pointer' : 'grab')}
      />
      <div className="map-tooltip" ref={tipRef} style={{ display: hoverNode ? 'block' : 'none' }}>
        {hoverNode && (
          <>
            <b>{hoverNode.title}</b>
            <div>{hoverNode.authors.slice(0, 3).map((a) => a.name).join(', ')}{hoverNode.authors.length > 3 ? ' et al.' : ''}</div>
            <div>{hoverNode.abbr} {hoverNode.year} · cited {hoverNode.cited}×</div>
            <div className="tip-disc">{hoverNode.discipline}</div>
          </>
        )}
      </div>
      <button className="map-reset" onClick={resetView}>Reset view</button>
      {selectedId != null && (
        <div className="map-key">
          <span><i style={{ background: CITES_COLOR }} /> cites</span>
          <span><i style={{ background: CITED_BY_COLOR }} /> cited by</span>
        </div>
      )}
    </div>
  )
}
