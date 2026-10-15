// Pure labeling logic for the panels: what the selection's labels look like, applying a
// label, progress per attribute and the box-list filters. Attributes always come from the
// taxonomy; no label names are hardcoded here.

import type { Draft } from 'immer'

import type { Annotation } from '../api/annotation'
import type { TaxonomyAttribute } from '../api/types'
import { completeness } from '../canvas/geometry'

export type BoxFilter = 'all' | 'empty' | 'partial' | 'done'

export interface LabelState {
  kind: 'none' | 'single' | 'mixed'
  /** The shared value when kind is 'single'. */
  value: string | null
  /** How many selected boxes have each value. */
  counts: Record<string, number>
  /** Selected boxes without this attribute. */
  unset: number
}

/** The selected boxes' values for one attribute. */
export function labelState(boxes: Annotation[], selectedIds: string[], attrId: string): LabelState {
  const selected = new Set(selectedIds)
  const counts: Record<string, number> = {}
  let unset = 0
  for (const box of boxes) {
    if (!selected.has(box.id)) continue
    const value = box.labels[attrId]
    if (value) counts[value] = (counts[value] ?? 0) + 1
    else unset += 1
  }
  const values = Object.keys(counts)
  if (values.length === 0) return { kind: 'none', value: null, counts, unset }
  if (values.length === 1 && unset === 0) return { kind: 'single', value: values[0], counts, unset }
  return { kind: 'mixed', value: null, counts, unset }
}

/**
 * Set (or with `value` null, remove) one attribute on a box draft, recording that a human
 * chose it. A relabeled legacy or machine box becomes `edited`, so evaluations can tell
 * corrected suggestions apart from accepted ones.
 */
export function applyLabel(
  box: Draft<Annotation>,
  attrId: string,
  value: string | null,
  now: string,
): void {
  const current = box.labels[attrId] ?? null
  if (current === value) return
  if (value === null) {
    delete box.labels[attrId]
    if (box.label_sources) delete box.label_sources[attrId]
  } else {
    box.labels[attrId] = value
    box.label_sources = { ...box.label_sources, [attrId]: 'human' }
  }
  if (box.source !== 'human' || box.status === 'suggested') box.status = 'edited'
  box.updated_at = now
}

const live = (boxes: Annotation[]) => boxes.filter((b) => b.status !== 'rejected')

export interface AttributeProgress {
  id: string
  label: string
  labeled: number
  total: number
}

/** Boxes with a value, per attribute. Rejected boxes don't count. */
export function attributeProgress(
  boxes: Annotation[],
  attributes: TaxonomyAttribute[],
): AttributeProgress[] {
  const counted = live(boxes)
  return attributes.map((a) => ({
    id: a.id,
    label: a.label,
    labeled: counted.filter((b) => b.labels[a.id]).length,
    total: counted.length,
  }))
}

const FILTER_STATE = { empty: 'empty', partial: 'partial', done: 'complete' } as const

/** Indices (into `boxes`) of the boxes shown under a filter, in file order. */
export function filterBoxes(boxes: Annotation[], attributeIds: string[], filter: BoxFilter): number[] {
  const indices: number[] = []
  boxes.forEach((box, i) => {
    if (box.status === 'rejected') return
    if (filter === 'all' || completeness(box.labels, attributeIds) === FILTER_STATE[filter]) {
      indices.push(i)
    }
  })
  return indices
}

export function filterCounts(boxes: Annotation[], attributeIds: string[]): Record<BoxFilter, number> {
  const counts = { all: 0, empty: 0, partial: 0, done: 0 }
  for (const box of live(boxes)) {
    counts.all += 1
    const state = completeness(box.labels, attributeIds)
    counts[state === 'complete' ? 'done' : state] += 1
  }
  return counts
}

/**
 * Tab / Shift+Tab (v2's "next unannotated"): the next box after the selection, in file
 * order, that isn't complete. Wraps around; rejected boxes are skipped.
 */
export function nextIncomplete(
  boxes: Annotation[],
  attributeIds: string[],
  selectedIds: string[],
  direction: 1 | -1,
): string | null {
  const n = boxes.length
  if (n === 0) return null
  const selected = new Set(selectedIds)
  const positions = boxes.flatMap((b, i) => (selected.has(b.id) ? [i] : []))
  let start: number
  if (positions.length === 0) start = direction === 1 ? -1 : n
  else start = direction === 1 ? Math.max(...positions) : Math.min(...positions)
  for (let step = 1; step <= n; step++) {
    const box = boxes[(((start + direction * step) % n) + n) % n]
    if (box.status !== 'rejected' && completeness(box.labels, attributeIds) !== 'complete') {
      return box.id
    }
  }
  return null
}

/** "Typo · Link · …" in taxonomy order. */
export function boxSummary(box: Annotation, attributeIds: string[]): string {
  return attributeIds
    .map((id) => box.labels[id])
    .filter(Boolean)
    .join(' · ')
}
