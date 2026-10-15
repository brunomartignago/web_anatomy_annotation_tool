import { useMemo } from 'react'
import { useShallow } from 'zustand/react/shallow'

import type { Annotation } from '../api/annotation'
import type { KeymapPreset } from '../keyboard/keymap'
import { useAppStore } from '../state/store'

const NO_BOXES: Annotation[] = []

/** "Typo · Text · Blank": the preset's values in taxonomy order. */
function presetSummary(labels: Record<string, string>, attributeIds: string[]): string {
  const ordered = attributeIds.filter((id) => id in labels)
  const extra = Object.keys(labels).filter((id) => !attributeIds.includes(id))
  return [...ordered, ...extra].map((id) => labels[id]).join(' · ')
}

/**
 * The taxonomy's presets (digits 1-9): each applies a whole label combination to every
 * selected box. The preset the selection already matches is marked.
 */
export function PresetPanel({
  presets,
  attributeIds,
}: {
  presets: KeymapPreset[]
  attributeIds: string[]
}) {
  const { boxes, selectedIds } = useAppStore(
    useShallow((s) => ({
      boxes: s.page?.annotations.annotations ?? NO_BOXES,
      selectedIds: s.selectedIds,
    })),
  )
  const { applyPreset } = useAppStore.getState()
  const selectedBoxes = useMemo(() => {
    const selected = new Set(selectedIds)
    return boxes.filter((b) => selected.has(b.id))
  }, [boxes, selectedIds])

  const matches = (labels: Record<string, string>) =>
    selectedBoxes.length > 0 &&
    selectedBoxes.every((box) => Object.entries(labels).every(([k, v]) => box.labels[k] === v))

  return (
    <section className="panel" aria-label="Presets panel">
      <h2 className="panel__title">Presets</h2>
      <div className="presets" role="group" aria-label="Presets">
        {presets.map((preset) => {
          const summary = presetSummary(preset.labels, attributeIds)
          return (
            <button
              key={preset.key}
              type="button"
              className="presets__item"
              aria-label={`Preset ${preset.key}: ${summary}`}
              aria-pressed={matches(preset.labels)}
              disabled={selectedIds.length === 0}
              onClick={() => applyPreset(preset.labels)}
            >
              <kbd className="labels__key" aria-hidden="true">
                {preset.key}
              </kbd>
              {summary}
            </button>
          )
        })}
      </div>
    </section>
  )
}
