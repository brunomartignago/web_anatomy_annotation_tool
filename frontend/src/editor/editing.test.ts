import { beforeEach, describe, expect, it } from 'vitest'

import type { Annotation } from '../api/annotation'
import type { PageResponse, PageSummary } from '../api/types'
import { initialState, useAppStore } from '../state/store'

const store = () => useAppStore.getState()

function box(id: string, y: number): Annotation {
  return { id, kind: 'element', bbox: [0, y, 100, 50], labels: {}, source: 'legacy', status: 'accepted' }
}

function pageResponse(boxes: Annotation[]): PageResponse {
  return {
    project: 'demo',
    etag: '"v1"',
    has_dom: false,
    strips: { height: 2048, count: 1 },
    annotations: {
      schema_version: '1.0',
      taxonomy: { id: 'web-ui', version: '1.0' },
      page: { id: 'p', image: 'page.png', width: 1920, height: 2000 },
      annotations: boxes,
    },
  }
}

const progress = { boxes: 1, empty: 1, partial: 0, complete: 0, suggested: 0, labeled: {} }
const row = (id: string): PageSummary => ({
  id,
  blocked: false,
  blocked_reasons: [],
  has_annotations: false,
  has_image: true,
  has_dom: false,
  strips: 1,
  progress: { ...progress, boxes: 0, empty: 0 },
})

const ids = () => store().page!.annotations.annotations.map((a) => a.id)

describe('editing', () => {
  beforeEach(() => {
    useAppStore.setState(initialState)
    store().pageLoaded('p', pageResponse([box('a', 0), box('b', 100), box('c', 200)]))
  })

  it('adds a human box, selects it and marks the page for saving', () => {
    const id = store().addBox([10, 20, 30, 40])!
    const added = store().page!.annotations.annotations.at(-1)!
    expect(added).toMatchObject({
      id,
      bbox: [10, 20, 30, 40],
      labels: {},
      source: 'human',
      status: 'accepted',
      kind: 'element',
    })
    expect(added.created_at).toMatch(/Z$/)
    expect(store().selectedIds).toEqual([id])
    expect(store().docVersion).toBe(1)
    expect(store().saveState).toBe('pending')
  })

  it('deletes the selection and undo brings back the exact boxes', () => {
    store().select(['a', 'c'])
    store().deleteSelected()
    expect(ids()).toEqual(['b'])
    expect(store().selectedIds).toEqual([])

    store().undo()
    expect(ids()).toEqual(['a', 'b', 'c'])
    expect(store().page!.annotations.annotations[0]).toEqual(box('a', 0))
    store().redo()
    expect(ids()).toEqual(['b'])
  })

  it('every change bumps the version, undo and redo included (AUDIT #7)', () => {
    store().addBox([0, 0, 10, 10])
    store().undo()
    store().redo()
    expect(store().docVersion).toBe(3)
  })

  it('deleting with nothing selected changes nothing', () => {
    store().deleteSelected()
    expect(store().docVersion).toBe(0)
    expect(store().history.undo).toHaveLength(0)
  })

  it('undo drops selected boxes that no longer exist', () => {
    const id = store().addBox([0, 0, 10, 10])!
    store().select([id, 'a'])
    store().undo()
    expect(store().selectedIds).toEqual(['a'])
  })

  it('selects by replace, add and toggle', () => {
    store().select(['a'])
    store().select(['b'], 'add')
    expect(store().selectedIds).toEqual(['a', 'b'])
    store().select(['a', 'c'], 'toggle')
    expect(store().selectedIds).toEqual(['b', 'c'])
    store().select(['c'])
    expect(store().selectedIds).toEqual(['c'])
  })

  it('labels every selected box in one undo step', () => {
    store().select(['a', 'c'])
    store().setLabel('Form', 'Typo')
    const labels = store().page!.annotations.annotations.map((b) => b.labels.Form)
    expect(labels).toEqual(['Typo', undefined, 'Typo'])
    expect(store().page!.annotations.annotations[0].status).toBe('edited') // was legacy
    expect(store().docVersion).toBe(1)

    store().undo()
    expect(store().page!.annotations.annotations.every((b) => !b.labels.Form)).toBe(true)
  })

  it('labeling with nothing selected, or to the same value, records nothing', () => {
    store().setLabel('Form', 'Typo')
    expect(store().docVersion).toBe(0)
    store().select(['a'])
    store().setLabel('Form', 'Typo')
    store().setLabel('Form', 'Typo')
    expect(store().history.undo).toHaveLength(1)
  })

  it('a preset sets every attribute it names, on every selected box, as one step', () => {
    store().select(['a', 'b'])
    store().applyPreset({ Form: 'Typo', Function: 'Text', Component: 'Blank' })
    for (const id of ['a', 'b']) {
      const b = store().page!.annotations.annotations.find((x) => x.id === id)!
      expect(b.labels).toEqual({ Form: 'Typo', Function: 'Text', Component: 'Blank' })
      expect(b.label_sources).toEqual({ Form: 'human', Function: 'human', Component: 'human' })
    }
    expect(store().history.undo).toHaveLength(1)
    store().undo()
    expect(store().page!.annotations.annotations.every((b) => !b.labels.Form)).toBe(true)
  })

  it('a preset keeps attributes it does not name (e.g. the template section)', () => {
    store().select(['a'])
    store().setLabel('Taxonomy', 'Header')
    store().applyPreset({ Form: 'Image', Function: 'Link', Component: 'Blank' })
    expect(store().page!.annotations.annotations[0].labels.Taxonomy).toBe('Header')
  })

  it('a preset with nothing selected does nothing', () => {
    store().applyPreset({ Form: 'Typo' })
    expect(store().docVersion).toBe(0)
  })

  it('opening a page starts a fresh history', () => {
    store().addBox([0, 0, 10, 10])
    store().pageLoaded('q', pageResponse([]))
    expect(store().history.undo).toHaveLength(0)
    expect(store().docVersion).toBe(0)
    expect(store().saveState).toBe('saved')
  })

  it('a save records the new etag and updates the page row', () => {
    useAppStore.setState({ pages: [row('p')] })
    store().addBox([0, 0, 10, 10])
    store().saveStarted()
    store().saveSucceeded('p', 1, '"v2"', progress)
    expect(store().page!.etag).toBe('"v2"')
    expect(store().saveState).toBe('saved')
    expect(store().pages[0].progress.boxes).toBe(1)
    expect(store().pages[0].has_annotations).toBe(true)
  })

  it('a save that finishes after more edits leaves the page pending', () => {
    store().addBox([0, 0, 10, 10])
    store().saveStarted()
    store().addBox([20, 0, 10, 10]) // edited while the first save was in flight
    store().saveSucceeded('p', 1, '"v2"', progress)
    expect(store().saveState).toBe('pending')
  })

  it("a late save for another page doesn't touch the open page", () => {
    store().addBox([0, 0, 10, 10])
    store().pageLoaded('q', pageResponse([]))
    store().saveSucceeded('p', 1, '"v9"', progress)
    expect(store().page!.etag).toBe('"v1"')
    expect(store().pageId).toBe('q')
  })
})
