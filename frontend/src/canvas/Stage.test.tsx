import { act, fireEvent, render } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'

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

// v2 parity (2.6): Tab navigation, Ctrl+S, toolbar, cursor coordinates.
describe('Stage parity with the legacy tool', () => {
  beforeEach(() => {
    useAppStore.setState({ ...initialState, project: 'demo' })
    useAppStore.getState().pageLoaded('tall', PAGE)
  })
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  const store = () => useAppStore.getState()

  it('Tab / Shift+Tab select the next / previous box that needs labels', () => {
    render(<StoreStage />)
    const tab = (shiftKey = false) =>
      act(() => {
        fireEvent.keyDown(window, { key: 'Tab', shiftKey })
      })
    tab() // a is complete, so the first box needing labels is b
    expect(store().selectedIds).toEqual(['b'])
    expect(store().focus?.id).toBe('b')
    tab()
    expect(store().selectedIds).toEqual(['c'])
    tab(true)
    expect(store().selectedIds).toEqual(['b'])
  })

  it('Ctrl+S saves right away instead of opening the browser dialog', async () => {
    const fetchMock = vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            etag: '"v2"',
            progress: { boxes: 4, empty: 1, partial: 1, complete: 2, suggested: 0, labeled: {} },
          }),
        ),
    )
    vi.stubGlobal('fetch', fetchMock)
    render(<StoreStage />)
    act(() => {
      store().addBox([0, 0, 50, 50])
    })
    const event = new KeyboardEvent('keydown', { key: 's', ctrlKey: true, cancelable: true })
    await act(async () => {
      window.dispatchEvent(event)
    })
    expect(event.defaultPrevented).toBe(true)
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(store().saveState).toBe('saved')
  })

  it('has clickable tools, undo/redo, delete and zoom', async () => {
    const { getByRole } = render(<StoreStage />)
    const button = (name: string) => getByRole('button', { name })
    expect(button('Undo')).toBeDisabled()
    expect(button('Delete')).toBeDisabled()

    await userEvent.click(button('Select'))
    expect(store().tool).toBe('select')
    expect(button('Select')).toHaveAttribute('aria-pressed', 'true')

    act(() => {
      store().select(['a'])
    })
    await userEvent.click(button('Delete'))
    expect(store().page!.annotations.annotations.map((b) => b.id)).toEqual(['b', 'c'])
    await userEvent.click(button('Undo'))
    expect(store().page!.annotations.annotations).toHaveLength(3)
    await userEvent.click(button('Redo'))
    expect(store().page!.annotations.annotations).toHaveLength(2)

    await userEvent.click(button('Zoom in'))
    expect(store().zoom).toBeCloseTo(0.625)
    await userEvent.click(button('Fit'))
    expect(store().zoom).toBe(0.5)
  })

  it('pans with middle-drag', () => {
    const { getByLabelText } = render(<StoreStage />)
    const viewport = getByLabelText('Page canvas')
    viewport.scrollTop = 1000
    act(() => {
      fireEvent.pointerDown(viewport, { button: 1, clientX: 300, clientY: 300 })
      fireEvent.pointerMove(viewport, { clientX: 250, clientY: 100 })
      fireEvent.pointerUp(viewport, { clientX: 250, clientY: 100 })
    })
    expect(viewport.scrollTop).toBe(1200) // dragged up 200 px → content moves up
    expect(store().page!.annotations.annotations).toHaveLength(3) // nothing drawn
  })

  it('draws index tags just above each box', () => {
    const { container } = render(<StoreStage />)
    const group = container.querySelector('[data-box-id="a"]')!
    const box = Number(group.querySelectorAll('rect')[0].getAttribute('y'))
    const tag = Number(group.querySelectorAll('rect')[1].getAttribute('y'))
    expect(box).toBe(50) // y 100 at zoom 0.5
    expect(tag).toBe(36) // 14 px tag, ending where the box starts
  })

  it('Shift+D draws a section box (3.4a)', () => {
    const { getByLabelText, getByRole } = render(<StoreStage />)
    act(() => {
      fireEvent.keyDown(window, { key: 'D', shiftKey: true })
    })
    expect(store().tool).toBe('section')
    expect(getByRole('status')).toHaveTextContent('Section (Shift+D)')
    const viewport = getByLabelText('Page canvas')
    act(() => {
      fireEvent.pointerDown(viewport, { button: 0, clientX: 0, clientY: 0 })
      fireEvent.pointerMove(viewport, { clientX: 960, clientY: 200 })
      fireEvent.pointerUp(viewport, { clientX: 960, clientY: 200 })
    })
    const added = store().page!.annotations.annotations.at(-1)!
    expect(added).toMatchObject({ kind: 'section', bbox: [0, 0, 1920, 400] })
    act(() => {
      fireEvent.keyDown(window, { key: 'd' })
    })
    expect(store().tool).toBe('draw')
  })

  it('draws sections first, dashed, tagged with the value they pass on', () => {
    useAppStore.setState({
      taxonomy: {
        id: 'web-ui',
        version: '1.0',
        name: 'test',
        presets: [],
        rules: {},
        attributes: ATTRIBUTES.map((id) => ({
          id,
          label: id,
          hotkey: id[0].toLowerCase(),
          options: [],
          inherit_from_parent: id === 'Component' || id === 'Taxonomy',
          computed_by_rules: false,
        })),
      },
    })
    act(() => {
      store().addBox([0, 0, 1920, 400], 'section')
      store().setLabel('Taxonomy', 'Header')
    })
    const { container } = render(<StoreStage />)
    const groups = [...container.querySelectorAll('[data-box-id]')]
    expect(groups[0].getAttribute('data-kind')).toBe('section') // under the boxes inside it
    const rect = groups[0].querySelector('rect')!
    expect(rect.getAttribute('stroke-dasharray')).toBe('8 4')
    expect(groups[0].querySelector('text')).toHaveTextContent('4 Header')
    // Box c inherited Header, but only the section's tag names it.
    const c = container.querySelector('[data-box-id="c"]')!
    expect(c.querySelector('text')).toHaveTextContent(/^3$/)
  })

  it('shows the cursor position in page pixels', () => {
    const { getByLabelText } = render(<StoreStage />)
    act(() => {
      fireEvent.pointerMove(getByLabelText('Page canvas'), { clientX: 100, clientY: 50 })
    })
    expect(getByLabelText('Cursor position')).toHaveTextContent('x 200 · y 100') // zoom 0.5
  })
})

function StoreStage() {
  const page = useAppStore((s) => s.page)!
  return <Stage project="demo" pageId="tall" page={page} attributeIds={ATTRIBUTES} />
}
