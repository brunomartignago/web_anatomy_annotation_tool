import { useMemo } from 'react'
import { useShallow } from 'zustand/react/shallow'

import type { Annotation } from '../api/annotation'
import { PAINT_PICKER } from '../keyboard/keymap'
import type { KeymapPreset } from '../keyboard/keymap'
import { useAppStore } from '../state/store'
import { presetSummary } from './labels'

const NO_BOXES: Annotation[] = []

/**
 * The taxonomy's presets (digits 1-9): each applies a whole label combination to every
 * selected box. The preset the selection already matches is marked. The brush next to each
 * one paints with it (3.5): every box clicked on the canvas gets the preset, until Esc.
 */
export function PresetPanel({
  presets,
  attributeIds,
}: {
  presets: KeymapPreset[]
  attributeIds: string[]
}) {
  const { boxes, selectedIds, paint, picker } = useAppStore(
    useShallow((s) => ({
      boxes: s.page?.annotations.annotations ?? NO_BOXES,
      selectedIds: s.selectedIds,
      paint: s.paint,
      picker: s.picker,
    })),
  )
  const { applyPreset, setPaint } = useAppStore.getState()
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
      {picker === PAINT_PICKER && (
        <p className="panel__prompt" role="status">
          Paint: press a preset digit · Esc cancels
        </p>
      )}
      {paint && (
        <p className="panel__prompt panel__prompt--paint" role="status">
          Painting preset {paint.key}: click or drag over boxes · Esc stops
        </p>
      )}
      <div className="presets" role="group" aria-label="Presets">
        {presets.map((preset) => {
          const summary = presetSummary(preset.labels, attributeIds)
          const painting = paint?.key === preset.key
          return (
            <div key={preset.key} className="presets__row">
              <button
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
              <button
                type="button"
                className="presets__paint"
                aria-label={`Paint with preset ${preset.key}`}
                aria-pressed={painting}
                title={
                  painting
                    ? 'Stop painting (Esc)'
                    : `Paint: every box you click gets this preset (p ${preset.key})`
                }
                onClick={() => setPaint(painting ? null : preset)}
              >
                <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
                  <path
                    d="M13.5 1.5 6 9l1 1 7.5-7.5a.7.7 0 0 0-1-1ZM5 10c-1.7 0-3 1.2-3 3 0 .6-.3 1.1-1 1.5 2.8.6 5-.6 5-3.5Z"
                    fill="currentColor"
                  />
                </svg>
              </button>
            </div>
          )
        })}
      </div>
    </section>
  )
}
