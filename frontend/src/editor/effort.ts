// Effort metrics (3.7), the project's main KPI: actions per box. v2 needed at least 5 per
// box (draw plus 4 picks); the target is about 1.5 (docs/ARCHITECTURE.md).
//
// An action is one command that changes the page: draw, label, preset, paint, delete, move
// or resize, kind change, and also undo and redo (they are effort too). Selecting is not.
// The count lives in the page file's `history.actions`, outside the undo history, so undo
// never lowers it.

import type { Draft } from 'immer'

import type { Annotation, PageAnnotationFileV1 } from '../api/annotation'

/** Add one action to the page's count. */
export function countAction(doc: Draft<PageAnnotationFileV1>): void {
  doc.history = { ...doc.history, actions: (doc.history?.actions ?? 0) + 1 }
}

/**
 * Boxes whose effort was spent in this tool: element boxes that are accepted or edited.
 * Untouched legacy boxes are left out (their effort was spent in v2), and so are
 * suggestions, rejected boxes and section/component containers.
 */
const doneHere = (box: Annotation) =>
  box.kind === 'element' &&
  (box.status === 'edited' || (box.status === 'accepted' && box.source !== 'legacy'))

export interface Effort {
  actions: number
  boxes: number
  /** Actions per box, or null when no box is done yet. */
  perBox: number | null
}

export function effort(doc: PageAnnotationFileV1): Effort {
  const actions = doc.history?.actions ?? 0
  const boxes = doc.annotations.filter(doneHere).length
  return { actions, boxes, perBox: boxes > 0 ? actions / boxes : null }
}
