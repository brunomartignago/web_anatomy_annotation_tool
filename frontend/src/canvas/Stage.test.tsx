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

// Editing (2.4). At zoom 0.5 a screen point (cx, cy) is page point (2cx, 2cy).
describe('Stage editing', () => {
  beforeEach(() => {
    useAppStore.setState(initialState)
    useAppStore.getState().pageLoaded('tall', PAGE)
  })

  const editing = () => {
    // Render against the store's page so edits show up.
    const utils = render(<StoreStage />)
    const viewport = utils.getByLabelText('Page canvas')
    const drag = (from: [number, number], to: [number, number], shiftKey = false) => {
      act(() => {
        fireEvent.pointerDown(viewport, { button: 0, clientX: from[0], clientY: from[1], shiftKey })
        fireEvent.pointerMove(viewport, { clientX: to[0], clientY: to[1] })
        fireEvent.pointerUp(viewport, { clientX: to[0], clientY: to[1] })
      })
    }
    const click = (x: number, y: number, shiftKey = false) => drag([x, y], [x, y], shiftKey)
    const key = (k: string, extra: Record<string, boolean> = {}) =>
      act(() => {
        fireEvent.keyDown(window, { key: k, ...extra })
      })
    return { ...utils, drag, click, key }
  }

  const store = () => useAppStore.getState()
  const boxIds = () => store().page!.annotations.annotations.map((a) => a.id)

  it('draws a box in draw mode (the default)', () => {
    const { drag } = editing()
    drag([100, 100], [300, 250])
    const added = store().page!.annotations.annotations.at(-1)!
    expect(added.bbox).toEqual([200, 200, 400, 300])
    expect(store().selectedIds).toEqual([added.id])
  })

  it('ignores tiny drags when drawing', () => {
    const { drag } = editing()
    drag([100, 100], [101, 101])
    expect(boxIds()).toEqual(['a', 'b', 'c'])
  })

  it('selects the smallest box under a click, Shift toggles', () => {
    useAppStore.getState().pageLoaded('tall', {
      ...PAGE,
      annotations: {
        ...PAGE.annotations,
        annotations: [
          { ...box('card', 0, {}), bbox: [0, 0, 1000, 1000] },
          { ...box('link', 0, {}), bbox: [100, 100, 200, 40] },
        ],
      },
    })
    const { click, key } = editing()
    key('s')
    click(60, 60) // page (120, 120): inside both, the link is smaller
    expect(store().selectedIds).toEqual(['link'])
    click(400, 400, true) // page (800, 800): only the card
    expect(store().selectedIds).toEqual(['link', 'card'])
    click(60, 60, true)
    expect(store().selectedIds).toEqual(['card'])
    click(900, 900) // empty space clears
    expect(store().selectedIds).toEqual([])
  })

  it('rubber-band selects every box it touches', () => {
    const { drag, key } = editing()
    key('s')
    drag([0, 0], [200, 130]) // page (0,0)-(400,260): boxes a (y 100) and c (y 200)
    expect(store().selectedIds).toEqual(['a', 'c'])
  })

  it('deletes the selection and Ctrl+Z / Ctrl+Shift+Z undo and redo it', () => {
    const { drag, key } = editing()
    key('s')
    drag([0, 0], [200, 130])
    key('Delete')
    expect(boxIds()).toEqual(['b'])
    key('z', { ctrlKey: true })
    expect(boxIds()).toEqual(['a', 'b', 'c'])
    key('z', { ctrlKey: true, shiftKey: true })
    expect(boxIds()).toEqual(['b'])
    key('y', { ctrlKey: true })
    expect(boxIds()).toEqual(['b']) // nothing left to redo
  })

  it('X deletes too, and Escape clears the selection', () => {
    const { click, key } = editing()
    key('s')
    click(50, 60) // box a
    key('Escape')
    expect(store().selectedIds).toEqual([])
    click(50, 60)
    key('x')
    expect(boxIds()).toEqual(['b', 'c'])
  })

  it('shows the tool, selection and save state', () => {
    const { getByRole, click, key } = editing()
    expect(getByRole('status')).toHaveTextContent('Draw (D)')
    key('s')
    click(50, 60)
    expect(getByRole('status')).toHaveTextContent('Select (S) · 1 selected')
    key('x')
    expect(getByRole('status')).toHaveTextContent('Unsaved changes')
  })
})

function StoreStage() {
  const page = useAppStore((s) => s.page)!
  return <Stage project="demo" pageId="tall" page={page} attributeIds={ATTRIBUTES} />
}
