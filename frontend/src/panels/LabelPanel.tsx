import { useEffect, useRef } from 'react'
import { useShallow } from 'zustand/react/shallow'

import type { Annotation } from '../api/annotation'
import type { TaxonomyAttribute } from '../api/types'
import { useAppStore } from '../state/store'
import { labelState } from './labels'

const NO_BOXES: Annotation[] = []

/**
 * One group per taxonomy attribute; clicking an option labels every selected box.
 * `hotkeys` (attribute id → key) shows the keyboard shortcuts generated from the YAML; the
 * group whose picker is open is highlighted so the focused attribute is always visible.
 */
export function LabelPanel({
  attributes,
  hotkeys = {},
}: {
  attributes: TaxonomyAttribute[]
  hotkeys?: Record<string, string>
}) {
  const { boxes, selectedIds, picker } = useAppStore(
    useShallow((s) => ({
      boxes: s.page?.annotations.annotations ?? NO_BOXES,
      selectedIds: s.selectedIds,
      picker: s.picker,
    })),
  )
  const { setLabel } = useAppStore.getState()
  const count = selectedIds.length
  const pickerLabel = attributes.find((a) => a.id === picker)?.label
  const panelRef = useRef<HTMLElement>(null)

  // The attribute being picked must always be visible, even in a scrolled inspector.
  useEffect(() => {
    if (!picker) return
    const group = panelRef.current?.querySelector('.labels--active')
    if (group instanceof HTMLElement) group.scrollIntoView?.({ block: 'nearest' })
  }, [picker])

  return (
    <section ref={panelRef} className="panel" aria-label="Labels">
      <h2 className="panel__title">
        Labels {count > 0 && <span className="panel__meta">{count} selected</span>}
      </h2>
      {count === 0 && <p className="panel__hint">Select boxes on the canvas to label them.</p>}
      {pickerLabel && (
        <p className="panel__prompt" role="status">
          {pickerLabel}: press a letter · Esc cancels
        </p>
      )}
      {attributes.map((attribute) => {
        const state = labelState(boxes, selectedIds, attribute.id)
        // Proposed options stay hidden (web-ui.yaml) unless a selected box already uses one.
        const options = attribute.options.filter(
          (o) => o.status === 'active' || state.counts[o.value],
        )
        const active = picker === attribute.id
        const hotkey = hotkeys[attribute.id]
        return (
          <fieldset
            key={attribute.id}
            className={active ? 'labels labels--active' : 'labels'}
            disabled={count === 0}
            // Explicit names: the key hints inside are visual only.
            aria-label={attribute.label}
            aria-current={active ? 'true' : undefined}
          >
            <legend>
              {attribute.label}
              {hotkey && (
                <kbd className="labels__hotkey" aria-hidden="true">
                  {hotkey}
                </kbd>
              )}
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
                    aria-label={state.kind === 'mixed' && n > 0 ? `${option.value} ${n}` : option.value}
                    aria-pressed={chosen}
                    title={option.note ?? undefined}
                    // Clicking the value already set keeps it; removing is the × button,
                    // so confirming a label can never delete it by accident.
                    onClick={() => setLabel(attribute.id, option.value)}
                  >
                    {hotkey && option.status === 'active' && (
                      <kbd className="labels__key" aria-hidden="true">
                        {option.key}
                      </kbd>
                    )}
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
