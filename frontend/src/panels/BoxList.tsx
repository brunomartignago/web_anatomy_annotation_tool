import { useEffect, useMemo, useRef, useState } from 'react'
import type { MouseEvent } from 'react'
import { useShallow } from 'zustand/react/shallow'

import type { Annotation } from '../api/annotation'
import { boxColor, completeness } from '../canvas/geometry'
import { useAppStore } from '../state/store'
import { boxSummary, filterBoxes, filterCounts } from './labels'
import type { BoxFilter } from './labels'

const NO_BOXES: Annotation[] = []
const FILTERS: { id: BoxFilter; label: string }[] = [
  { id: 'all', label: 'All' },
  { id: 'empty', label: 'Empty' },
  { id: 'partial', label: 'Partial' },
  { id: 'done', label: 'Done' },
]

/** Every box on the page, filterable by completeness; a click selects and shows it. */
export function BoxList({ attributeIds }: { attributeIds: string[] }) {
  const { boxes, selectedIds } = useAppStore(
    useShallow((s) => ({
      boxes: s.page?.annotations.annotations ?? NO_BOXES,
      selectedIds: s.selectedIds,
    })),
  )
  const { select, focusBox } = useAppStore.getState()
  const [filter, setFilter] = useState<BoxFilter>('all')
  const counts = useMemo(() => filterCounts(boxes, attributeIds), [boxes, attributeIds])
  const shown = useMemo(
    () => filterBoxes(boxes, attributeIds, filter),
    [boxes, attributeIds, filter],
  )
  const selected = useMemo(() => new Set(selectedIds), [selectedIds])
  const listRef = useRef<HTMLOListElement>(null)

  // Keep the (first) selected box visible in the list, e.g. after picking it on the canvas.
  // Scrolls only the list itself: scrollIntoView would also scroll the whole inspector and
  // push the presets and labels out of view.
  useEffect(() => {
    const list = listRef.current
    const first = selectedIds[0]
    const row = first && list?.querySelector(`[data-box-id="${CSS.escape(first)}"]`)
    if (!list || !(row instanceof HTMLElement)) return
    const top = row.offsetTop // the list is the rows' offsetParent (position: relative)
    const bottom = top + row.offsetHeight
    if (top < list.scrollTop) list.scrollTop = top
    else if (bottom > list.scrollTop + list.clientHeight) list.scrollTop = bottom - list.clientHeight
  }, [selectedIds])

  const onClick = (event: MouseEvent, id: string) => {
    select([id], event.shiftKey ? 'toggle' : 'replace')
    focusBox(id)
  }

  return (
    <section className="panel panel--grow" aria-label="Boxes">
      <h2 className="panel__title">Boxes</h2>
      <div className="filters" role="group" aria-label="Filter boxes">
        {FILTERS.map((f) => (
          <button
            key={f.id}
            type="button"
            className="filters__button"
            aria-pressed={filter === f.id}
            onClick={() => setFilter(f.id)}
          >
            {f.label}{' '}
            <span className="filters__count">{counts[f.id]}</span>
          </button>
        ))}
      </div>
      {shown.length === 0 ? (
        <p className="panel__hint">No boxes here.</p>
      ) : (
        <ol ref={listRef} className="boxes" aria-label="Box list">
          {shown.map((i) => {
            const box = boxes[i]
            const color = boxColor(completeness(box.labels, attributeIds), false)
            const summary = boxSummary(box, attributeIds)
            return (
              <li key={box.id}>
                <button
                  type="button"
                  className="boxes__row"
                  data-box-id={box.id}
                  aria-label={`Box ${i + 1}: ${summary || 'unlabeled'}`}
                  aria-current={selected.has(box.id) ? 'true' : undefined}
                  onClick={(event) => onClick(event, box.id)}
                >
                  <span className="boxes__dot" style={{ background: color }} />
                  <span className="boxes__index">{i + 1}</span>
                  <span className={summary ? 'boxes__summary' : 'boxes__summary is-empty'}>
                    {summary || 'unlabeled'}
                  </span>
                </button>
              </li>
            )
          })}
        </ol>
      )}
    </section>
  )
}
