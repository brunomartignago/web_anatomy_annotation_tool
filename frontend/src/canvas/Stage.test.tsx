import { act, fireEvent, render } from '@testing-library/react'
import { afterAll, beforeAll, beforeEach, describe, expect, it } from 'vitest'

import type { Annotation } from '../api/annotation'
import type { PageResponse } from '../api/types'
import { initialState, useAppStore } from '../state/store'
import { Stage } from './Stage'

const ATTRIBUTES = ['Form', 'Function', 'Component', 'Taxonomy']
const COMPLETE = { Form: 'Typo', Function: 'Text', Component: 'Blank', Taxonomy: 'Header' }

function box(id: string, y: number, labels: Record<string, string>): Annotation {
  return { id, kind: 'element', bbox: [10, y, 300, 50], labels, source: 'human', status: 'accepted' }
}

const PAGE: PageResponse = {
  project: 'demo',
  etag: '"x"',
  has_dom: false,
  strips: { height: 2048, count: 5 },
  annotations: {
    schema_version: '1.0',
    taxonomy: { id: 'web-ui', version: '1.0' },
    page: { id: 'tall', image: 'page.png', width: 1920, height: 10000 },
    annotations: [
      box('a', 100, COMPLETE),
      box('b', 9000, {}),
      box('c', 200, { Form: 'Typo' }),
    ],
  },
}

// jsdom has no layout: pretend the canvas is 960 x 1000 px.
const originals = {
  width: Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'clientWidth'),
  height: Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'clientHeight'),
}
beforeAll(() => {
  Object.defineProperty(HTMLElement.prototype, 'clientWidth', { configurable: true, value: 960 })
  Object.defineProperty(HTMLElement.prototype, 'clientHeight', { configurable: true, value: 1000 })
})
afterAll(() => {
  if (originals.width) Object.defineProperty(HTMLElement.prototype, 'clientWidth', originals.width)
  if (originals.height)
    Object.defineProperty(HTMLElement.prototype, 'clientHeight', originals.height)
})

function renderStage() {
  const utils = render(
    <Stage project="demo" pageId="tall" page={PAGE} attributeIds={ATTRIBUTES} />,
  )
  const viewport = utils.getByLabelText('Page canvas')
  const strips = () =>
    [...utils.container.querySelectorAll('img.stage__strip')].map((img) =>
      (img as HTMLImageElement).getAttribute('src'),
    )
  const boxes = () =>
    [...utils.container.querySelectorAll('[data-box-id]')].map((g) => ({
      id: g.getAttribute('data-box-id'),
      color: g.querySelector('rect')?.getAttribute('stroke'),
      tag: g.querySelector('text')?.textContent,
    }))
  return { ...utils, viewport, strips, boxes }
}

describe('Stage', () => {
  beforeEach(() => {
    useAppStore.setState(initialState)
  })

  it('opens fitted to the width', () => {
    renderStage()
    expect(useAppStore.getState().zoom).toBe(0.5) // 960 / 1920
  })

  it('mounts only the strips near the viewport', () => {
    const { strips } = renderStage()
    // At zoom 0.5 a strip is 1024 screen px; 1000 px viewport + 800 px overscan → strips 0-1.
    expect(strips()).toEqual([
      '/api/pages/tall/strips/0.webp?project=demo',
      '/api/pages/tall/strips/1.webp?project=demo',
    ])
  })

  it('draws only boxes in view, colored by completeness, with index tags', () => {
    const { boxes } = renderStage()
    expect(boxes()).toEqual([
      { id: 'a', color: '#34d399', tag: '1' }, // complete
      { id: 'c', color: '#fbbf24', tag: '3' }, // partial
    ])
  })

  it('swaps strips and boxes as the page scrolls', () => {
    const { viewport, strips, boxes } = renderStage()
    act(() => {
      viewport.scrollTop = 4000
      fireEvent.scroll(viewport)
    })
    expect(strips().map((src) => src?.match(/strips\/(\d+)/)?.[1])).toEqual(['3', '4'])
    expect(boxes()).toEqual([{ id: 'b', color: '#f05252', tag: '2' }]) // empty, at y 9000
  })

  it('zooms with + and - and fits the width again with Ctrl+0', () => {
    renderStage()
    act(() => {
      fireEvent.keyDown(window, { key: '+' })
    })
    expect(useAppStore.getState().zoom).toBeCloseTo(0.625)
    act(() => {
      fireEvent.keyDown(window, { key: '-' })
      fireEvent.keyDown(window, { key: '-' })
    })
    expect(useAppStore.getState().zoom).toBeCloseTo(0.4)
    act(() => {
      fireEvent.keyDown(window, { key: '0', ctrlKey: true })
    })
    expect(useAppStore.getState().zoom).toBe(0.5)
  })

  it('zooms with Ctrl+wheel but scrolls normally without Ctrl', () => {
    const { viewport } = renderStage()
    act(() => {
      fireEvent.wheel(viewport, { deltaY: -200, ctrlKey: true })
    })
    expect(useAppStore.getState().zoom).toBeGreaterThan(0.5)
    const zoomed = useAppStore.getState().zoom
    act(() => {
      fireEvent.wheel(viewport, { deltaY: 200 })
    })
    expect(useAppStore.getState().zoom).toBe(zoomed)
  })

  it('shows zoom and page size in the status bar', () => {
    const { getByRole } = renderStage()
    expect(getByRole('status')).toHaveTextContent('50% · 3 boxes · 1920×10000 px')
  })
})
