import { describe, expect, it } from 'vitest'

import {
  MAX_ZOOM,
  MIN_ZOOM,
  boxColor,
  boxesInView,
  clampZoom,
  completeness,
  fitWidthZoom,
  visibleStrips,
  wheelZoomFactor,
  zoomAround,
} from './geometry'

describe('visibleStrips', () => {
  const base = { stripHeight: 2048, count: 45, overscanPx: 0 }

  it('returns only the strips under the viewport', () => {
    // 1000 px viewport at zoom 1, scrolled to 3000: rows 3000-4000 → strip 1 only.
    expect(visibleStrips({ ...base, scrollTop: 3000, viewportHeight: 1000, zoom: 1 })).toEqual([1])
    // Straddling the boundary at 4096.
    expect(visibleStrips({ ...base, scrollTop: 3500, viewportHeight: 1000, zoom: 1 })).toEqual([
      1, 2,
    ])
  })

  it('accounts for zoom', () => {
    // At zoom 0.5 a strip is 1024 screen px; screen 0-2100 → strips 0-2.
    expect(visibleStrips({ ...base, scrollTop: 0, viewportHeight: 2100, zoom: 0.5 })).toEqual([
      0, 1, 2,
    ])
  })

  it('adds overscan and stays within the page', () => {
    const strips = visibleStrips({
      ...base,
      count: 3,
      scrollTop: 0,
      viewportHeight: 500,
      zoom: 1,
      overscanPx: 2000,
    })
    expect(strips).toEqual([0, 1])
    expect(
      visibleStrips({ ...base, count: 3, scrollTop: 99999, viewportHeight: 500, zoom: 1 }),
    ).toEqual([])
  })

  it('keeps few strips mounted even on the 91,086 px page at minimum zoom', () => {
    const count = Math.ceil(91086 / 2048) // 45 strips
    const strips = visibleStrips({
      stripHeight: 2048,
      count,
      scrollTop: 20000,
      viewportHeight: 1200,
      zoom: MIN_ZOOM,
      overscanPx: 1200,
    })
    expect(strips.length).toBeLessThanOrEqual(20)
  })
})

describe('zoom', () => {
  it('clamps to the allowed range', () => {
    expect(clampZoom(100)).toBe(MAX_ZOOM)
    expect(clampZoom(0.0001)).toBe(MIN_ZOOM)
    expect(clampZoom(1)).toBe(1)
  })

  it('fits the page width into the container', () => {
    expect(fitWidthZoom(960, 1920)).toBe(0.5)
    expect(fitWidthZoom(100, 1920)).toBe(MIN_ZOOM)
  })

  it('wheel up zooms in, wheel down zooms out', () => {
    expect(wheelZoomFactor(-100)).toBeGreaterThan(1)
    expect(wheelZoomFactor(100)).toBeLessThan(1)
    expect(wheelZoomFactor(-100) * wheelZoomFactor(100)).toBeCloseTo(1)
  })

  it('keeps the page point under the cursor still', () => {
    const before = { zoom: 1, scrollLeft: 100, scrollTop: 5000 }
    const anchor = { x: 300, y: 400 } // cursor, relative to the scroll container
    const after = zoomAround({ ...before, newZoom: 2, anchorX: anchor.x, anchorY: anchor.y })
    // Page point under the cursor: (400, 5400) before → still under it after.
    expect((after.scrollLeft + anchor.x) / 2).toBeCloseTo(400)
    expect((after.scrollTop + anchor.y) / 2).toBeCloseTo(5400)
  })

  it('never scrolls to negative positions', () => {
    const after = zoomAround({
      zoom: 1,
      newZoom: 0.5,
      scrollLeft: 0,
      scrollTop: 0,
      anchorX: 500,
      anchorY: 500,
    })
    expect(after.scrollLeft).toBe(0)
    expect(after.scrollTop).toBe(0)
  })
})

describe('boxes', () => {
  const boxes = [
    { bbox: [0, 0, 100, 50] as [number, number, number, number] },
    { bbox: [0, 5000, 100, 50] as [number, number, number, number] },
    { bbox: [0, 9000, 100, 2000] as [number, number, number, number] },
  ]

  it('finds the boxes overlapping a vertical range of the page', () => {
    expect(boxesInView(boxes, 4900, 6000)).toEqual([1])
    expect(boxesInView(boxes, 10000, 10500)).toEqual([2]) // tall box spanning the view
    expect(boxesInView(boxes, 200, 300)).toEqual([])
  })

  const attributes = ['Form', 'Function', 'Component', 'Taxonomy']

  it('rates completeness against the taxonomy attributes', () => {
    expect(completeness({}, attributes)).toBe('empty')
    expect(completeness({ Form: 'Typo' }, attributes)).toBe('partial')
    expect(
      completeness(
        { Form: 'Typo', Function: 'Text', Component: 'Blank', Taxonomy: 'Header' },
        attributes,
      ),
    ).toBe('complete')
  })

  it('colors selection over completeness', () => {
    expect(boxColor('empty', false)).not.toBe(boxColor('complete', false))
    expect(boxColor('empty', true)).toBe(boxColor('complete', true))
  })
})
