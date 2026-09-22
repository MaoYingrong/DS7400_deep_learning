import { useEffect, useRef, useState } from 'react'

export const PRESET_TAGS = ['Important', 'To read', 'Relevant to my research', 'Method', 'Question']

/**
 * Tag + note editor for one paper. Tags toggle on click; the note saves automatically
 * (shortly after you stop typing, and when you click away). Everything is stored in the backend database.
 */
export default function AnnotationEditor({ doi, saved, onSave, backendOnline }) {
  const [tags, setTags] = useState(saved?.tags ?? [])
  const [note, setNote] = useState(saved?.note ?? '')
  const [customTag, setCustomTag] = useState('')
  const [status, setStatus] = useState('') // '', 'Saving…', 'Saved ✓', or an error
  const latest = useRef({ tags, note })
  const dirty = useRef(false)
  const timer = useRef(null)

  const save = async (next) => {
    latest.current = next
    dirty.current = false
    setStatus('Saving…')
    try {
      await onSave(doi, next)
      setStatus('Saved ✓')
    } catch (e) {
      setStatus(`Not saved: ${e.message}`)
    }
  }

  // If the user selects another paper mid-typing, save what they typed before this editor goes away.
  useEffect(() => () => {
    clearTimeout(timer.current)
    if (dirty.current) onSave(doi, latest.current).catch(() => {})
  }, [doi, onSave])

  const changeTags = (next) => {
    setTags(next)
    save({ tags: next, note })
  }
  const toggle = (t) => changeTags(tags.includes(t) ? tags.filter((x) => x !== t) : [...tags, t])
  const addCustom = () => {
    const t = customTag.trim().replace(/\s+/g, ' ')
    setCustomTag('')
    if (t && !tags.some((x) => x.toLowerCase() === t.toLowerCase())) changeTags([...tags, t])
  }
  const changeNote = (value) => {
    setNote(value)
    latest.current = { tags, note: value }
    dirty.current = true
    setStatus('')
    clearTimeout(timer.current)
    timer.current = setTimeout(() => save({ tags, note: value }), 800)
  }

  const shown = [...PRESET_TAGS, ...tags.filter((t) => !PRESET_TAGS.includes(t))]
  return (
    <section className="annotation">
      <h3>My annotation {status && <span className={status.startsWith('Not') ? 'save-status err' : 'save-status'}>{status}</span>}</h3>
      {!backendOnline ? (
        <p className="muted">Backend is offline, so annotations can't be saved. Start it with <code>uvicorn backend.app.main:app --port 8000</code>.</p>
      ) : (
        <>
          <div className="chips" role="group" aria-label="Tags">
            {shown.map((t) => (
              <button key={t} className={tags.includes(t) ? 'chip on' : 'chip'} aria-pressed={tags.includes(t)} onClick={() => toggle(t)}>
                {tags.includes(t) ? '★ ' : ''}{t}
              </button>
            ))}
          </div>
          <div className="add-tag">
            <input
              value={customTag} maxLength={40} placeholder="Add your own tag…" aria-label="Add a custom tag"
              onChange={(e) => setCustomTag(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && addCustom()}
            />
            <button onClick={addCustom} disabled={!customTag.trim()}>Add</button>
          </div>
          <textarea
            rows={3} maxLength={2000} placeholder="Write a note about this paper…" aria-label="Note" value={note}
            onChange={(e) => changeNote(e.target.value)} onBlur={() => dirty.current && save({ tags, note })}
          />
        </>
      )}
    </section>
  )
}
