// Undo/redo with immer patches: each step stores only what changed, not a copy of the
// whole page (the legacy tool deep-copied every box on every edit).

import { applyPatches, enablePatches, produceWithPatches } from 'immer'
import type { Draft, Patch } from 'immer'

enablePatches()

export const HISTORY_LIMIT = 200

interface Step {
  patches: Patch[]
  inverse: Patch[]
}

export interface History {
  undo: Step[]
  redo: Step[]
}

export const emptyHistory = (): History => ({ undo: [], redo: [] })

/** Apply `recipe` to `doc`, recording the step. A recipe that changes nothing records none. */
export function edit<T>(
  doc: T,
  history: History,
  recipe: (draft: Draft<T>) => void,
): { doc: T; history: History } {
  const [next, patches, inverse] = produceWithPatches(doc, recipe)
  if (patches.length === 0) return { doc, history }
  return {
    doc: next as T,
    history: { undo: [...history.undo, { patches, inverse }].slice(-HISTORY_LIMIT), redo: [] },
  }
}

export function undo<T>(doc: T, history: History): { doc: T; history: History } | null {
  const step = history.undo.at(-1)
  if (!step) return null
  return {
    doc: applyPatches(doc as object, step.inverse) as T,
    history: { undo: history.undo.slice(0, -1), redo: [...history.redo, step] },
  }
}

export function redo<T>(doc: T, history: History): { doc: T; history: History } | null {
  const step = history.redo.at(-1)
  if (!step) return null
  return {
    doc: applyPatches(doc as object, step.patches) as T,
    history: { undo: [...history.undo, step], redo: history.redo.slice(0, -1) },
  }
}
