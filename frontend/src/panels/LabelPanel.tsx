import { useShallow } from 'zustand/react/shallow'

import type { Annotation } from '../api/annotation'
import type { TaxonomyAttribute } from '../api/types'
import { useAppStore } from '../state/store'
import { labelState } from './labels'

const NO_BOXES: Annotation[] = []

/** One group per taxonomy attribute; clicking an option labels every selected box. */
export function LabelPanel({ attributes }: { attributes: TaxonomyAttribute[] }) {
  const { boxes, selectedIds } = useAppStore(
    useShallow((s) => ({
      boxes: s.page?.annotations.annotations ?? NO_BOXES,
      selectedIds: s.selectedIds,
    })),
  )
  const { setLabel } = useAppStore.getState()
  const count = selectedIds.length

  return (
    <section className="panel" aria-label="Labels">
      <h2 className="panel__title">
        Labels {count > 0 && <span className="panel__meta">{count} selected</span>}
      </h2>
      {count === 0 && <p className="panel__hint">Select boxes on the canvas to label them.</p>}
      {attributes.map((attribute) => {
        const state = labelState(boxes, selectedIds, attribute.id)
        // Proposed options stay hidden (web-ui.yaml) unless a selected box already uses one.
        const options = attribute.options.filter(
          (o) => o.status === 'active' || state.counts[o.value],
        )
        return (
          <fieldset key={attribute.id} className="labels" disabled={count === 0}>
            <legend>
              {attribute.label}
              {state.kind === 'mixed' && <span className="labels__mixed">mixed</span>}
              {state.kind !== 'none' && (
                <button
                  type="button"
                  className="labels__clear"
                  aria-label={`Clear ${attribute.label}`}
                  title={`Remove ${attribute.label} from the selected boxes`}
                  onClick={() => setLabel(attribute.id, null)}
                >
                  ×
                </button>
              )}
            </legend>
            <div className="labels__options">
              {options.map((option) => {
                const chosen = state.kind === 'single' && state.value === option.value
                const n = state.counts[option.value] ?? 0
                return (
                  <button
                    key={option.value}
                    type="button"
                    className="labels__option"
                    aria-pressed={chosen}
                    title={option.note ?? undefined}
                    // Clicking the value already set keeps it; removing is the × button,
                    // so confirming a label can never delete it by accident.
                    onClick={() => setLabel(attribute.id, option.value)}
                  >
                    {option.value}
                    {state.kind === 'mixed' && n > 0 && (
                      <>
                        {' '}
                        <span className="labels__count">{n}</span>
                      </>
                    )}
                  </button>
                )
              })}
            </div>
          </fieldset>
        )
      })}
    </section>
  )
}
