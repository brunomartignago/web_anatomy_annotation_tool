import { produce } from 'immer'
import { describe, expect, it } from 'vitest'

import type { Annotation, PageAnnotationFileV1 } from '../api/annotation'
import type { BBox } from '../canvas/geometry'
import { applyInheritance, isContainer } from './inheritance'

// From web-ui.yaml: Component and Taxonomy have inherit_from_parent: true.
const INHERITABLE = ['Component', 'Taxonomy']

function box(
  id: string,
  kind: Annotation['kind'],
  bbox: BBox,
  labels: Record<string, string> = {},
  label_sources?: Annotation['label_sources'],
): Annotation {
  return { id, kind, bbox, labels, label_sources, source: 'human', status: 'accepted' }
}

function doc(...annotations: Annotation[]): PageAnnotationFileV1 {
  return {
    schema_version: '1.0',
    taxonomy: { id: 'web-ui', version: '1.0' },
    page: { id: 'p', image: 'page.png', width: 1920, height: 5000 },
    annotations,
  }
}

const run = (d: PageAnnotationFileV1) => produce(d, (draft) => applyInheritance(draft, INHERITABLE))
const get = (d: PageAnnotationFileV1, id: string) => d.annotations.find((a) => a.id === id)!

const header = box('header', 'section', [0, 0, 1920, 300], { Taxonomy: 'Header' })
const footer = box('footer', 'section', [0, 4000, 1920, 1000], { Taxonomy: 'Footer' })

describe('inheritance (3.4a)', () => {
  it('an element inside a labeled section inherits its template section', () => {
    const out = run(doc(header, box('logo', 'element', [20, 20, 100, 50], { Form: 'Image' })))
    const logo = get(out, 'logo')
    expect(logo.labels).toEqual({ Form: 'Image', Taxonomy: 'Header' })
    expect(logo.label_sources).toEqual({ Taxonomy: 'inherited' })
    expect(logo.parent_id).toBe('header')
  })

  it('the smallest containing box wins', () => {
    const column = box('col', 'section', [0, 300, 960, 3700], { Taxonomy: 'Column 1' })
    const body = box('body', 'section', [0, 300, 1920, 3700], { Taxonomy: 'Column 0' })
    const out = run(doc(body, column, box('text', 'element', [50, 500, 200, 40])))
    expect(get(out, 'text').labels.Taxonomy).toBe('Column 1')
    expect(get(out, 'text').parent_id).toBe('col')
  })

  it('components pass on Component; the section above still passes on Taxonomy', () => {
    const card = box('card', 'component', [100, 1000, 400, 300], { Component: 'Card' })
    const body = box('body', 'section', [0, 300, 1920, 3700], { Taxonomy: 'Column 0' })
    const out = run(doc(body, card, box('title', 'element', [120, 1020, 300, 40])))
    expect(get(out, 'title').labels).toEqual({ Component: 'Card', Taxonomy: 'Column 0' })
    expect(get(out, 'title').parent_id).toBe('card')
    expect(get(out, 'card').labels.Taxonomy).toBe('Column 0') // the card itself sits in the body
  })

  it('an explicit label from any other source is never overwritten', () => {
    const out = run(
      doc(
        header,
        box('mine', 'element', [20, 20, 50, 50], { Taxonomy: 'Sub-header' }, { Taxonomy: 'human' }),
        box('old', 'element', [80, 20, 50, 50], { Taxonomy: 'Column 0' }, { Taxonomy: 'legacy' }),
        box('nosource', 'element', [140, 20, 50, 50], { Taxonomy: 'Footer' }),
      ),
    )
    expect(get(out, 'mine').labels.Taxonomy).toBe('Sub-header')
    expect(get(out, 'old').labels.Taxonomy).toBe('Column 0')
    expect(get(out, 'nosource').labels.Taxonomy).toBe('Footer')
  })

  it('relabeling the section updates the inherited children', () => {
    const before = run(doc(header, box('logo', 'element', [20, 20, 100, 50])))
    const relabeled = produce(before, (d) => {
      d.annotations[0].labels.Taxonomy = 'Sub-header'
      applyInheritance(d, INHERITABLE)
    })
    expect(get(relabeled, 'logo').labels.Taxonomy).toBe('Sub-header')
  })

  it('clearing or deleting the section removes what the children inherited', () => {
    const before = run(doc(header, box('logo', 'element', [20, 20, 100, 50], { Form: 'Image' })))

    const cleared = produce(before, (d) => {
      delete d.annotations[0].labels.Taxonomy
      applyInheritance(d, INHERITABLE)
    })
    expect(get(cleared, 'logo').labels).toEqual({ Form: 'Image' })
    expect(get(cleared, 'logo').label_sources).toEqual({})
    expect(get(cleared, 'logo').parent_id).toBe('header') // still inside the (unlabeled) section

    const deleted = produce(before, (d) => {
      d.annotations.splice(0, 1)
      applyInheritance(d, INHERITABLE)
    })
    expect(get(deleted, 'logo').labels).toEqual({ Form: 'Image' })
    expect(get(deleted, 'logo').parent_id).toBeUndefined()
  })

  it('only attributes marked inherit_from_parent are inherited', () => {
    const section = box('s', 'section', [0, 0, 1920, 300], { Taxonomy: 'Header', Form: 'Typo' })
    const out = run(doc(section, box('e', 'element', [20, 20, 100, 50])))
    expect(get(out, 'e').labels).toEqual({ Taxonomy: 'Header' })
  })

  it('an element whose centre is outside the section gets nothing', () => {
    // Overlaps the header's bottom edge, but its centre (y = 340) is below it.
    const out = run(doc(header, footer, box('e', 'element', [20, 280, 100, 120])))
    expect(get(out, 'e').labels).toEqual({})
    expect(get(out, 'e').parent_id).toBeUndefined()
  })

  it('changes nothing (no undo step) when everything is already up to date', () => {
    const once = run(doc(header, footer, box('logo', 'element', [20, 20, 100, 50])))
    expect(run(once)).toBe(once)
    const untouched = doc(box('a', 'element', [0, 0, 10, 10]))
    expect(run(untouched)).toBe(untouched)
  })

  it('knows which boxes are containers', () => {
    expect(isContainer(header)).toBe(true)
    expect(isContainer(box('c', 'component', [0, 0, 1, 1]))).toBe(true)
    expect(isContainer(box('e', 'element', [0, 0, 1, 1]))).toBe(false)
  })
})
