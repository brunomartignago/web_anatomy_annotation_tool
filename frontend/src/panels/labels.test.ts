import { produce } from 'immer'
import { describe, expect, it } from 'vitest'

import type { Annotation } from '../api/annotation'
import type { TaxonomyAttribute } from '../api/types'
import {
  applyLabel,
  attributeProgress,
  boxSummary,
  filterBoxes,
  filterCounts,
  labelState,
} from './labels'

function box(id: string, labels: Record<string, string>, extra: Partial<Annotation> = {}) {
  return {
    id,
    kind: 'element',
    bbox: [0, 0, 10, 10],
    labels,
    source: 'human',
    status: 'accepted',
    ...extra,
  } as Annotation
}

const attr = (id: string, values: string[]): TaxonomyAttribute => ({
  id,
  label: id,
  hotkey: id[0].toLowerCase(),
  options: values.map((value, i) => ({ value, key: String(i), status: 'active' })),
  inherit_from_parent: false,
  computed_by_rules: false,
})

const ATTRS = [attr('Form', ['Typo', 'Image']), attr('Function', ['Text', 'Link'])]
const IDS = ATTRS.map((a) => a.id)

describe('labelState', () => {
  const boxes = [
    box('a', { Form: 'Typo' }),
    box('b', { Form: 'Typo' }),
    box('c', { Form: 'Image' }),
    box('d', {}),
  ]

  it('reports a single shared value', () => {
    const state = labelState(boxes, ['a', 'b'], 'Form')
    expect(state.kind).toBe('single')
    expect(state.value).toBe('Typo')
  })

  it('reports mixed values with counts, including unlabeled boxes', () => {
    const state = labelState(boxes, ['a', 'c', 'd'], 'Form')
    expect(state.kind).toBe('mixed')
    expect(state.counts).toEqual({ Typo: 1, Image: 1 })
    expect(state.unset).toBe(1)
  })

  it('reports none when no selected box has the attribute', () => {
    expect(labelState(boxes, ['d'], 'Form').kind).toBe('none')
    expect(labelState(boxes, [], 'Form').kind).toBe('none')
  })
})

describe('applyLabel', () => {
  const NOW = '2026-10-15T12:00:00.000Z'

  it('sets the value, marks it as human and stamps the time', () => {
    const next = produce(box('a', {}), (d) => applyLabel(d, 'Form', 'Typo', NOW))
    expect(next.labels).toEqual({ Form: 'Typo' })
    expect(next.label_sources).toEqual({ Form: 'human' })
    expect(next.updated_at).toBe(NOW)
    expect(next.status).toBe('accepted') // a human box stays accepted
  })

  it('a relabeled machine or legacy box becomes edited', () => {
    for (const source of ['legacy', 'dom', 'rule'] as const) {
      const start = box('a', { Form: 'Image' }, { source, status: 'accepted' })
      const next = produce(start, (d) => applyLabel(d, 'Form', 'Typo', NOW))
      expect(next.status).toBe('edited')
    }
  })

  it('a reviewed suggestion stops being "suggested"', () => {
    const start = box('a', {}, { source: 'dom', status: 'suggested' })
    const next = produce(start, (d) => applyLabel(d, 'Form', 'Typo', NOW))
    expect(next.status).toBe('edited')
  })

  it('null removes the label and its source', () => {
    const start = box('a', { Form: 'Typo', Function: 'Text' }, { label_sources: { Form: 'human' } })
    const next = produce(start, (d) => applyLabel(d, 'Form', null, NOW))
    expect(next.labels).toEqual({ Function: 'Text' })
    expect(next.label_sources).toEqual({})
  })

  it('setting the same value again changes nothing', () => {
    const start = box('a', { Form: 'Typo' }, { source: 'legacy' })
    const next = produce(start, (d) => applyLabel(d, 'Form', 'Typo', NOW))
    expect(next).toBe(start)
  })
})

describe('progress and filters', () => {
  const boxes = [
    box('empty', {}),
    box('partial', { Form: 'Typo' }),
    box('done', { Form: 'Typo', Function: 'Text' }),
    box('rejected', { Form: 'Typo', Function: 'Text' }, { status: 'rejected' }),
  ]

  it('counts labeled boxes per attribute, ignoring rejected ones', () => {
    expect(attributeProgress(boxes, ATTRS)).toEqual([
      { id: 'Form', label: 'Form', labeled: 2, total: 3 },
      { id: 'Function', label: 'Function', labeled: 1, total: 3 },
    ])
  })

  it('filters boxes by completeness, keeping their file order', () => {
    expect(filterBoxes(boxes, IDS, 'all')).toEqual([0, 1, 2])
    expect(filterBoxes(boxes, IDS, 'empty')).toEqual([0])
    expect(filterBoxes(boxes, IDS, 'partial')).toEqual([1])
    expect(filterBoxes(boxes, IDS, 'done')).toEqual([2])
    expect(filterCounts(boxes, IDS)).toEqual({ all: 3, empty: 1, partial: 1, done: 1 })
  })

  it('summarizes a box in taxonomy order', () => {
    expect(boxSummary(box('x', { Function: 'Link', Form: 'Image' }), IDS)).toBe('Image · Link')
    expect(boxSummary(box('x', {}), IDS)).toBe('')
  })
})
