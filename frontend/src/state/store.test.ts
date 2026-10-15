import { beforeEach, describe, expect, it } from 'vitest'

import type { PageSummary, Taxonomy } from '../api/types'
import { initialState, useAppStore } from './store'

const taxonomy: Taxonomy = {
  id: 'web-ui',
  version: '1.0',
  name: 'Test taxonomy',
  attributes: [],
  presets: [],
  rules: {},
}

function page(id: string): PageSummary {
  return {
    id,
    blocked: false,
    blocked_reasons: [],
    has_annotations: false,
    has_image: true,
    has_dom: true,
    strips: 1,
    progress: { boxes: 0, empty: 0, partial: 0, complete: 0, suggested: 0, labeled: {} },
  }
}

const store = () => useAppStore.getState()

describe('app store', () => {
  beforeEach(() => {
    useAppStore.setState(initialState)
  })

  it('opens the first page once pages are loaded', () => {
    store().loaded(taxonomy, 'demo', [page('a'), page('b')])
    expect(store().status).toBe('ready')
    expect(store().project).toBe('demo')
    expect(store().currentPageId).toBe('a')
  })

  it('keeps the open page across reloads if it still exists', () => {
    store().loaded(taxonomy, 'demo', [page('a'), page('b')])
    store().openPage('b')
    store().loaded(taxonomy, 'demo', [page('a'), page('b'), page('c')])
    expect(store().currentPageId).toBe('b')
  })

  it('ignores unknown page ids', () => {
    store().loaded(taxonomy, 'demo', [page('a')])
    store().openPage('nope')
    expect(store().currentPageId).toBe('a')
  })

  it('steps through the queue and stops at the ends', () => {
    store().loaded(taxonomy, 'demo', [page('a'), page('b'), page('c')])
    store().stepPage(1)
    store().stepPage(1)
    expect(store().currentPageId).toBe('c')
    store().stepPage(1)
    expect(store().currentPageId).toBe('c')
    store().stepPage(-1)
    expect(store().currentPageId).toBe('b')
  })

  it('records load errors', () => {
    store().startLoading()
    store().failed('boom')
    expect(store().status).toBe('error')
    expect(store().error).toBe('boom')
  })
})
