import { useMemo } from 'react'

import type { Annotation } from '../api/annotation'
import type { TaxonomyAttribute } from '../api/types'
import { useAppStore } from '../state/store'
import { attributeProgress, filterCounts } from './labels'

const NO_BOXES: Annotation[] = []

/** How far labeling has got on this page: complete boxes, then each attribute. */
export function ProgressPanel({ attributes }: { attributes: TaxonomyAttribute[] }) {
  const boxes = useAppStore((s) => s.page?.annotations.annotations ?? NO_BOXES)
  const ids = useMemo(() => attributes.map((a) => a.id), [attributes])
  const rows = useMemo(() => attributeProgress(boxes, attributes), [boxes, attributes])
  const counts = useMemo(() => filterCounts(boxes, ids), [boxes, ids])

  return (
    <section className="panel" aria-label="Progress">
      <h2 className="panel__title">Progress</h2>
      <Bar label="Complete boxes" done={counts.done} total={counts.all} strong />
      {rows.map((row) => (
        <Bar key={row.id} label={row.label} done={row.labeled} total={row.total} />
      ))}
    </section>
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
