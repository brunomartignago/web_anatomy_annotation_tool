import { useMemo } from 'react'

import type { Annotation, PageAnnotationFileV1 } from '../api/annotation'
import type { TaxonomyAttribute } from '../api/types'
import { effort } from '../editor/effort'
import { useAppStore } from '../state/store'
import { attributeProgress, filterCounts } from './labels'

const NO_BOXES: Annotation[] = []

/**
 * How far labeling has got on this page: complete boxes, then each attribute. Counts
 * element boxes only; section and component boxes are containers, not work to label.
 */
export function ProgressPanel({ attributes }: { attributes: TaxonomyAttribute[] }) {
  const page = useAppStore((s) => s.page?.annotations ?? null)
  const boxes = page?.annotations ?? NO_BOXES
  const ids = useMemo(() => attributes.map((a) => a.id), [attributes])
  const rows = useMemo(() => attributeProgress(boxes, attributes), [boxes, attributes])
  const counts = useMemo(() => filterCounts(boxes, ids), [boxes, ids])

  return (
    <section className="panel" aria-label="Progress">
      <h2 className="panel__title">Progress</h2>
      <Bar label="Complete boxes" done={counts.done} total={counts.elements} strong />
      {rows.map((row) => (
        <Bar key={row.id} label={row.label} done={row.labeled} total={row.total} />
      ))}
      {page && <EffortLine page={page} />}
    </section>
  )
}

/**
 * The main KPI (3.7): actions per box done in this tool. v2 needed at least 5 per box
 * (draw plus 4 picks), and the target is about 1.5.
 */
function EffortLine({ page }: { page: PageAnnotationFileV1 }) {
  const { actions, boxes, perBox } = effort(page)
  return (
    <p
      className="progress__effort"
      aria-label="Effort"
      title={
        'Actions (draws, labels, presets, deletes, moves, undo/redo) per box labeled in this ' +
        `tool: ${actions} actions over ${boxes} boxes. v2 needed 5 or more; the target is 1.5.`
      }
    >
      <span>Effort</span>
      <span>
        {actions} {actions === 1 ? 'action' : 'actions'} ·{' '}
        <strong>{perBox === null ? '—' : perBox.toFixed(1)}</strong> per box
      </span>
    </p>
  )
}

function Bar(props: { label: string; done: number; total: number; strong?: boolean }) {
  const percent = props.total ? Math.round((props.done / props.total) * 100) : 0
  return (
    <div className={props.strong ? 'progress progress--strong' : 'progress'}>
      <div className="progress__text">
        <span>{props.label}</span>
        <span>
          {props.done}/{props.total}
        </span>
      </div>
      <div
        className="progress__track"
        role="progressbar"
        aria-label={props.label}
        aria-valuemin={0}
        aria-valuemax={props.total}
        aria-valuenow={props.done}
      >
        <div className="progress__fill" style={{ width: `${percent}%` }} />
      </div>
    </div>
  )
}
