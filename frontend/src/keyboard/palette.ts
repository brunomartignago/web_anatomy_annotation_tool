// Command palette search: every active taxonomy value and every preset, found by fuzzy
// matching ("hea" → Heading, "rmen" → Right Menu). Generated from the keymap, which comes
// from the taxonomy YAML.

import type { Keymap } from './keymap'

export type Command =
  | {
      id: string
      kind: 'label'
      title: string // the value, e.g. "Heading"
      detail: string // the attribute, e.g. "Function"
      shortcut: string // e.g. "n h"
      attribute: string
      value: string
    }
  | {
      id: string
      kind: 'preset'
      title: string // e.g. "Typo · Text · Blank"
      detail: string // e.g. "Preset 1"
      shortcut: string // e.g. "1"
      labels: Record<string, string>
    }

/** All commands in taxonomy order: each attribute's active values, then the presets. */
export function buildCommands(keymap: Keymap): Command[] {
  const commands: Command[] = []
  for (const attribute of keymap.attributes) {
    for (const option of attribute.options) {
      commands.push({
        id: `label:${attribute.id}:${option.value}`,
        kind: 'label',
        title: option.value,
        detail: attribute.label,
        shortcut: `${attribute.hotkey} ${option.key}`,
        attribute: attribute.id,
        value: option.value,
      })
    }
  }
  for (const preset of keymap.presets) {
    commands.push({
      id: `preset:${preset.key}`,
      kind: 'preset',
      title: Object.values(preset.labels).join(' · '),
      detail: `Preset ${preset.key}`,
      shortcut: preset.key,
      labels: preset.labels,
    })
  }
  return commands
}

const isWordStart = (text: string, i: number) => i === 0 || /[\s·\-_/]/.test(text[i - 1])

/**
 * How well `query`'s letters appear, in order, in `text` (case-insensitive); null if they
 * don't. Matches at the very start, at word starts and in runs score higher.
 */
export function fuzzyScore(query: string, text: string): number | null {
  const q = query.toLowerCase().replace(/\s+/g, '')
  const t = text.toLowerCase()
  if (!q) return 0
  let score = 0
  let from = 0
  let previous = -2
  for (const ch of q) {
    const i = t.indexOf(ch, from)
    if (i < 0) return null
    score += 1
    if (i === 0) score += 5
    else if (isWordStart(t, i)) score += 3
    if (i === previous + 1) score += 2
    previous = i
    from = i + 1
  }
  return score
}

/**
 * Commands matching every word of `query`, best first; ties keep taxonomy order, so "hea"
 * lists Heading (Function) before Header (Template section). Each word may match the title
 * or the attribute, so "section foot" finds Footer.
 */
export function searchCommands(commands: Command[], query: string): Command[] {
  const words = query.trim().split(/\s+/).filter(Boolean)
  if (words.length === 0) return commands
  const scored: { command: Command; score: number; index: number }[] = []
  commands.forEach((command, index) => {
    let total = 0
    for (const word of words) {
      // The title counts more than the attribute name it belongs to.
      const inTitle = fuzzyScore(word, command.title)
      const inDetail = fuzzyScore(word, command.detail)
      if (inTitle === null && inDetail === null) return
      total += Math.max(inTitle === null ? -Infinity : inTitle * 2, inDetail ?? -Infinity)
    }
    scored.push({ command, score: total, index })
  })
  scored.sort((a, b) => b.score - a.score || a.index - b.index)
  return scored.map((s) => s.command)
}
