import { useEffect, useRef, useState } from 'react'
import { fetchModel, fetchTrainStatus, startTraining, stopTraining, resetModel } from '../api'

/** Minimal SVG line chart: `series` = [{name, color, values}], x = epoch number. */
function LineChart({ title, series, yLabel, yMin }) {
  const W = 330, H = 170, m = { l: 40, r: 10, t: 22, b: 26 }
  const n = Math.max(1, ...series.map((s) => s.values.length))
  const all = series.flatMap((s) => s.values)
  const lo = yMin ?? Math.min(0, ...all), hi = Math.max(...all, lo + 1e-6)
  const x = (i) => m.l + (n <= 1 ? 0 : (i / (n - 1)) * (W - m.l - m.r))
  const y = (v) => H - m.b - ((v - lo) / (hi - lo)) * (H - m.t - m.b)
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="chart" role="img" aria-label={title}>
      <text x={m.l} y={13} className="chart-title">{title}</text>
      {[0, 0.5, 1].map((t) => {
        const v = lo + t * (hi - lo)
        return <g key={t}><line x1={m.l} x2={W - m.r} y1={y(v)} y2={y(v)} stroke="#e6e4dc" /><text x={m.l - 4} y={y(v) + 3} textAnchor="end" className="chart-tick">{v.toFixed(2)}</text></g>
      })}
      <text x={(m.l + W - m.r) / 2} y={H - 4} textAnchor="middle" className="chart-tick">epoch (1–{n}) · {yLabel}</text>
      {series.map((s) => (
        <polyline key={s.name} fill="none" stroke={s.color} strokeWidth="2" points={s.values.map((v, i) => `${x(i)},${y(v)}`).join(' ')} />
      ))}
      {series.map((s, i) => (
        <g key={s.name} transform={`translate(${W - 150 + i * 70}, 13)`}><rect width="10" height="3" y="-2" fill={s.color} /><text x="14" y="2" className="chart-tick">{s.name}</text></g>
      ))}
    </svg>
  )
}

const pct = (v) => `${(v * 100).toFixed(1)}%`
const SERIES = [['train', '#2a78d6'], ['val', '#eb6834'], ['test', '#1baf7a']]

/** Overlay: model summary, live training monitor, and interactive hyper-parameter controls. */
export default function ModelPanel({ onClose, onModelChange }) {
  const [info, setInfo] = useState(null)
  const [hp, setHp] = useState(null)
  const [job, setJob] = useState(null) // live training status
  const [error, setError] = useState(null)
  const wasRunning = useRef(false)

  const load = () => fetchModel().then((m) => { setInfo(m); return m }).catch((e) => setError(e.message))
  useEffect(() => { load().then((m) => m && setHp(m.hparams)) }, [])

  // Poll the training job while it runs (also picks up a job that was started earlier).
  useEffect(() => {
    const tick = () => fetchTrainStatus().then((s) => {
      setJob(s)
      if (wasRunning.current && !s.running) { load(); onModelChange() }
      wasRunning.current = s.running
    }).catch(() => {})
    tick()
    const t = setInterval(tick, 500)
    return () => clearInterval(t)
  }, [])

  if (!info || !hp) return <div className="overlay"><div className="modal">{error ? `Error: ${error}` : 'Loading model…'}<button onClick={onClose}>Close</button></div></div>

  const running = job?.running
  const showJob = job && (job.running || job.history.length > 0)
  const history = showJob ? job.history : info.history
  const lim = info.limits
  const set = (k, v) => setHp({ ...hp, [k]: v })
  const num = (k, step) => (
    <input type="number" step={step} min={lim[k]?.[0]} max={lim[k]?.[1]} value={hp[k]} onChange={(e) => set(k, e.target.value === '' ? '' : Number(e.target.value))} disabled={running} />
  )
  const train = () => { setError(null); startTraining(hp).catch((e) => setError(e.message)) }
  const m = info.metrics, lr = info.baselines.logistic_regression, mc = info.baselines.majority_class

  return (
    <div className="overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-label="Neural network">
        <div className="modal-head">
          <h2>Neural network · field prediction</h2>
          <button className="toast-x" onClick={onClose} aria-label="Close">×</button>
        </div>
        <p className="muted small">
          An MLP ({info.hparams.n_layers} hidden layer{info.hparams.n_layers > 1 ? 's' : ''} × {info.hparams.hidden} units, {info.hparams.activation}) predicts a paper's
          discipline ({info.classes.length} classes) from its title, journal and its citation neighbours' titles. Active weights: <b>{info.source}</b>.
          Split: {info.split_sizes.train} train / {info.split_sizes.val} val / {info.split_sizes.test} test papers.
        </p>

        <div className="modal-grid">
          <div>
            <h3>Live training monitor {running && <span className="pulse">● training {job.epoch}/{job.epochs}</span>}</h3>
            <LineChart title="Loss (cross-entropy)" yLabel="loss" yMin={0} series={SERIES.map(([k, color]) => ({ name: k, color, values: history.map((h) => h[`${k}_loss`]) }))} />
            <LineChart title="Accuracy" yLabel="accuracy" yMin={0} series={SERIES.map(([k, color]) => ({ name: k, color, values: history.map((h) => h[`${k}_acc`]) }))} />
          </div>

          <div>
            <h3>Results (best-validation weights)</h3>
            <table className="metrics">
              <thead><tr><th></th><th>loss</th><th>accuracy</th><th>macro-F1</th></tr></thead>
              <tbody>
                {['train', 'val', 'test'].map((k) => (
                  <tr key={k} className={k === 'test' ? 'strong' : ''}><td>{k}</td><td>{m[k].loss.toFixed(3)}</td><td>{pct(m[k].accuracy)}</td><td>{m[k].macro_f1.toFixed(3)}</td></tr>
                ))}
              </tbody>
            </table>
            <h3>Shallow baselines (test)</h3>
            <table className="metrics">
              <thead><tr><th></th><th>error</th><th>accuracy</th><th>macro-F1</th></tr></thead>
              <tbody>
                <tr><td>majority class</td><td>{pct(mc.error)}</td><td>{pct(mc.accuracy)}</td><td>{mc.macro_f1.toFixed(3)}</td></tr>
                <tr><td>logistic regression</td><td>{pct(lr.error)}</td><td>{pct(lr.accuracy)}</td><td>{lr.macro_f1.toFixed(3)}</td></tr>
                <tr className="strong"><td>this MLP</td><td>{pct(m.test.error)}</td><td>{pct(m.test.accuracy)}</td><td>{m.test.macro_f1.toFixed(3)}</td></tr>
              </tbody>
            </table>
            <p className="small muted">{m.test.error < lr.error ? 'The MLP has a lower error than the shallow benchmark.' : 'The MLP does not beat the shallow benchmark with these settings.'}</p>

            <h3>Train your own</h3>
            <div className="hp-grid">
              <label>Learning rate{num('lr', 0.0005)}</label>
              <label>Epochs{num('epochs', 1)}</label>
              <label>Hidden units{num('hidden', 8)}</label>
              <label>Hidden layers{num('n_layers', 1)}</label>
              <label>Dropout{num('dropout', 0.1)}</label>
              <label>Activation
                <select value={hp.activation} onChange={(e) => set('activation', e.target.value)} disabled={running}>
                  {['relu', 'tanh', 'sigmoid', 'leaky_relu'].map((a) => <option key={a}>{a}</option>)}
                </select>
              </label>
              <label>Optimizer
                <select value={hp.optimizer} onChange={(e) => set('optimizer', e.target.value)} disabled={running}>
                  <option value="adam">Adam</option><option value="sgd">SGD + momentum</option>
                </select>
              </label>
            </div>
            <div className="btn-row">
              {running ? <button className="primary" onClick={() => stopTraining()}>Stop</button> : <button className="primary" onClick={train}>Train</button>}
              <button disabled={running} onClick={() => resetModel().then(() => { load().then((x) => x && setHp(x.hparams)); onModelChange() }).catch((e) => setError(e.message))}>Reset to pre-trained</button>
            </div>
            {error && <p className="small" style={{ color: '#b3261e' }}>{error}</p>}
            <p className="small muted">Training runs on the backend; the new weights are used for predictions in this session only.</p>
          </div>
        </div>
      </div>
    </div>
  )
}
