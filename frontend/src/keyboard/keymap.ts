// Label shortcuts generated from the taxonomy: an attribute's `hotkey` opens its picker,
// then an option's `key` sets it (two keystrokes for any active option), and a digit
// applies a whole preset (one keystroke). Nothing here names a label: it all comes from
// the YAML.

import type { Taxonomy, TaxonomyOption } from '../api/types'

/** Keys the app already uses on their own (no Ctrl/Alt). Digits are for presets (3.2). */
export const RESERVED_KEYS = new Set([
  'd', // draw tool
  's', // select tool
  'x', // delete
  '?', // cheat sheet
  '/', // command palette
  '[', // previous page
  ']', // next page
  '+',
  '=',
  '-',
  '_', // zoom
  ' ', // pan
  ...'0123456789',
])

export interface KeymapAttribute {
  id: string
  label: string
  hotkey: string
  options: TaxonomyOption[] // active ones only
}

export interface KeymapPreset {
  key: string
  labels: Record<string, string>
}

export interface Keymap {
  attributes: KeymapAttribute[]
  /** One-keystroke label combinations (digits), in YAML order. */
  presets: KeymapPreset[]
  /** Human-readable problems; conflicting hotkeys and invalid presets are left out. */
  conflicts: string[]
}

export type KeyAction =
  | { type: 'open'; attribute: string }
  | { type: 'set'; attribute: string; value: string }
  | { type: 'preset'; labels: Record<string, string> }
  | { type: 'close' }
  /** The key was used up by an open picker without doing anything. */
  | { type: 'none' }
  /** Not a label shortcut: let the rest of the app handle it. */
  | { type: 'pass' }

export function buildKeymap(taxonomy: Taxonomy): Keymap {
  const conflicts: string[] = []
  const attributes: KeymapAttribute[] = []
  for (const attribute of taxonomy.attributes) {
    const hotkey = attribute.hotkey.toLowerCase()
    if (RESERVED_KEYS.has(hotkey)) {
      conflicts.push(
        `${attribute.label}: hotkey "${attribute.hotkey}" is already used by the app; ` +
          'pick another one in the taxonomy YAML',
      )
      continue
    }
    attributes.push({
      id: attribute.id,
      label: attribute.label,
      hotkey,
      options: attribute.options.filter((o) => o.status !== 'proposed'),
    })
  }

  // Presets: a digit and labels that must all be active options. The server's loader
  // checks this too; here a bad preset is dropped with a warning rather than half-applied.
  const presets: KeymapPreset[] = []
  for (const preset of taxonomy.presets ?? []) {
    const problems = Object.entries(preset.labels).flatMap(([attrId, value]) => {
      const attribute = taxonomy.attributes.find((a) => a.id === attrId)
      const option = attribute?.options.find((o) => o.value === value)
      return option && option.status !== 'proposed' ? [] : [`${attrId} "${value}"`]
    })
    if (!/^[1-9]$/.test(preset.key)) {
      conflicts.push(`preset "${preset.key}": preset keys must be the digits 1-9`)
    } else if (problems.length > 0) {
      conflicts.push(`preset ${preset.key}: ${problems.join(', ')} is not an active option`)
    } else {
      presets.push({ key: preset.key, labels: { ...preset.labels } })
    }
  }
  return { attributes, presets, conflicts }
}

/** What a key press does, given which attribute's picker is open (if any). */
export function pressKey(keymap: Keymap, picker: string | null, key: string): KeyAction {
  const k = key.length === 1 ? key.toLowerCase() : key
  const byHotkey = keymap.attributes.find((a) => a.hotkey === k)

  if (picker === null) {
    if (byHotkey) return { type: 'open', attribute: byHotkey.id }
    const preset = keymap.presets.find((p) => p.key === k)
    return preset ? { type: 'preset', labels: preset.labels } : { type: 'pass' }
  }

  const open = keymap.attributes.find((a) => a.id === picker)
  if (k === 'Escape' || !open) return { type: 'close' }
  // Tab, Delete, Enter, arrows… keep their normal meaning while a picker is open.
  if (k.length !== 1) return { type: 'pass' }
  // Option letters win, so "c" in the Form picker is Icon, not the Component hotkey.
  const option = open.options.find((o) => o.key.toLowerCase() === k)
  if (option) return { type: 'set', attribute: open.id, value: option.value }
  if (byHotkey) {
    return byHotkey.id === open.id ? { type: 'close' } : { type: 'open', attribute: byHotkey.id }
  }
  return { type: 'none' }
}
