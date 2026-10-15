import { describe, expect, it } from 'vitest'

import type { Annotation, PageAnnotationFileV1 } from '../api/annotation'
import { effort } from './effort'

function box(id: string, extra: Partial<Annotation> = {}): Annotation {
  return { id, kind: 'element', bbox: [0, 0, 10, 10], labels: {}, source: 'human', status: 'accepted', ...extra }
}

function doc(boxes: Annotation[], actions?: number): PageAnnotationFileV1 {
  return {
    schema_version: '1.0',
    taxonomy: { id: 'web-ui', version: '1.0' },
    page: { id: 'p', image: 'page.png', width: 100, height: 100 },
    annotations: boxes,
    ...(actions === undefined ? {} : { history: { actions } }),
  }
}

describe('effort (3.7)', () => {
  it('divides actions by the element boxes done in this tool', () => {
    const boxes = [box('a'), box('b', { status: 'edited', source: 'dom' }), box('c'), box('d')]
    expect(effort(doc(boxes, 6))).toEqual({ actions: 6, boxes: 4, perBox: 1.5 })
  })

  it('leaves out untouched legacy boxes, but counts legacy boxes edited here', () => {
    const boxes = [
      box('old1', { source: 'legacy' }),
      box('old2', { source: 'legacy' }),
      box('fixed', { source: 'legacy', status: 'edited' }),
    ]
    expect(effort(doc(boxes, 2))).toEqual({ actions: 2, boxes: 1, perBox: 2 })
  })

  it('leaves out suggestions, rejected boxes, sections and components', () => {
    const boxes = [
      box('a'),
      box('s', { status: 'suggested', source: 'dom' }),
      box('r', { status: 'rejected' }),
      box('sec', { kind: 'section' }),
      box('card', { kind: 'component' }),
    ]
    expect(effort(doc(boxes, 3))).toMatchObject({ boxes: 1, perBox: 3 })
  })

  it('has no ratio without boxes, and treats a missing count as zero', () => {
    expect(effort(doc([], 4))).toEqual({ actions: 4, boxes: 0, perBox: null })
    expect(effort(doc([box('a')]))).toEqual({ actions: 0, boxes: 1, perBox: 0 })
  })
})
