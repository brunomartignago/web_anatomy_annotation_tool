import { useEffect, useRef } from 'react'
import { useShallow } from 'zustand/react/shallow'

import type { Annotation } from '../api/annotation'
import type { TaxonomyAttribute } from '../api/types'
import { useAppStore } from '../state/store'
import type { BoxKind } from '../state/store'
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
      {count > 0 && <KindSwitch boxes={boxes} selectedIds={selectedIds} />}
      {attributes.map((attribute) => {
        const state = labelState(boxes, selectedIds, attribute.id)
        const labeled = Object.values(state.counts).reduce((a, b) => a + b, 0)
        // Inherited values come back from the section, so × only clears values set here.
        const allInherited = labeled > 0 && state.inherited === labeled
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
              {allInherited && (
                <span
                  className="labels__inherited"
                  title="Passed on by the section or component around the box. Pick a value to override it."
                >
                  inherited
                </span>
              )}
              {state.kind !== 'none' && !allInherited && (
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

const KINDS: { kind: BoxKind; label: string; title: string }[] = [
  { kind: 'element', label: 'Element', title: 'A box to label (counts towards progress)' },
  {
    kind: 'section',
    label: 'Section',
    title: 'A template section: boxes inside inherit its Template section',
  },
  {
    kind: 'component',
    label: 'Component',
    title: 'A component (e.g. a card): boxes inside inherit its Component',
  },
]

/** Element / Section / Component for the selected boxes; pressed when they all share it. */
function KindSwitch({ boxes, selectedIds }: { boxes: Annotation[]; selectedIds: string[] }) {
  const { setKind } = useAppStore.getState()
  const selected = new Set(selectedIds)
  const kinds = new Set(boxes.filter((b) => selected.has(b.id)).map((b) => b.kind))
  const shared = kinds.size === 1 ? [...kinds][0] : null
  return (
    <div className="kind-switch" role="group" aria-label="Box kind">
      {KINDS.map(({ kind, label, title }) => (
        <button
          key={kind}
          type="button"
          className="kind-switch__option"
          aria-pressed={shared === kind}
          title={title}
          onClick={() => setKind(kind)}
        >
          {label}
        </button>
      ))}
    </div>
  )
}
