import { describe, expect, it } from 'vitest'

import type { BBox } from '../canvas/geometry'
import {
  MIN_BOX_SIZE,
  boxesCentredIn,
  boxesInRect,
  clampMove,
  handleAt,
  hitTest,
  rectFromDrag,
  resizeBBox,
  translate,
} from './geometry'

const card = { id: 'card', bbox: [100, 100, 400, 300] as BBox }
const link = { id: 'link', bbox: [150, 150, 100, 30] as BBox } // inside the card
const far = { id: 'far', bbox: [1000, 2000, 50, 50] as BBox }
const boxes = [card, link, far]

describe('hitTest', () => {
  it('returns the smallest box under the point', () => {
    expect(hitTest(boxes, 160, 160)).toBe('link') // inside both: the link is smaller
    expect(hitTest(boxes, 400, 350)).toBe('card')
  })

  it('returns null when nothing is under the point', () => {
    expect(hitTest(boxes, 5, 5)).toBeNull()
  })

  it('counts the edges as inside', () => {
    expect(hitTest(boxes, 100, 100)).toBe('card')
    expect(hitTest(boxes, 500, 400)).toBe('card')
  })
})

describe('boxesInRect', () => {
  it('selects every box the rubber band touches', () => {
    expect(boxesInRect(boxes, [0, 0, 120, 120])).toEqual(['card'])
    expect(boxesInRect(boxes, [140, 140, 20, 20])).toEqual(['card', 'link'])
    expect(boxesInRect(boxes, [0, 0, 2000, 3000])).toEqual(['card', 'link', 'far'])
    expect(boxesInRect(boxes, [600, 600, 10, 10])).toEqual([])
  })
})

describe('boxesCentredIn', () => {
  it('takes only boxes whose centre is inside, so a grazed neighbour is left alone', () => {
    expect(boxesCentredIn(boxes, [0, 0, 120, 120])).toEqual([]) // touches the card only
    expect(boxesCentredIn(boxes, [140, 140, 120, 60])).toEqual(['link']) // centre (200, 165)
    expect(boxesCentredIn(boxes, [0, 0, 2000, 3000])).toEqual(['card', 'link', 'far'])
  })
})

describe('rectFromDrag', () => {
  const page = { width: 1920, height: 5000 }

  it('normalizes any drag direction to [x, y, w, h]', () => {
    expect(rectFromDrag({ x: 10, y: 20 }, { x: 110, y: 70 }, page)).toEqual([10, 20, 100, 50])
    expect(rectFromDrag({ x: 110, y: 70 }, { x: 10, y: 20 }, page)).toEqual([10, 20, 100, 50])
    expect(rectFromDrag({ x: 110, y: 20 }, { x: 10, y: 70 }, page)).toEqual([10, 20, 100, 50])
  })

  it('clamps to the page', () => {
    expect(rectFromDrag({ x: -50, y: -10 }, { x: 30, y: 40 }, page)).toEqual([0, 0, 30, 40])
    expect(rectFromDrag({ x: 1900, y: 4990 }, { x: 2100, y: 5200 }, page)).toEqual([
      1900, 4990, 20, 10,
    ])
  })

  it('rounds to 0.1 px like the rest of the data', () => {
    expect(rectFromDrag({ x: 10.123, y: 20.456 }, { x: 50.789, y: 60.111 }, page)).toEqual([
      10.1, 20.5, 40.7, 39.7,
    ])
  })

  it('rejects drags smaller than the minimum size', () => {
    expect(rectFromDrag({ x: 10, y: 10 }, { x: 10 + MIN_BOX_SIZE - 1, y: 50 }, page)).toBeNull()
    expect(rectFromDrag({ x: 10, y: 10 }, { x: 50, y: 11 }, page)).toBeNull()
  })
})

// Move and resize (3.4b). The card is [100, 100, 400, 300]: edges x 100/500, y 100/400.
describe('handleAt', () => {
  const tol = 6

  it('finds corners first, then whole edges', () => {
    expect(handleAt(card.bbox, 100, 100, tol)).toBe('nw')
    expect(handleAt(card.bbox, 503, 404, tol)).toBe('se')
    expect(handleAt(card.bbox, 497, 98, tol)).toBe('ne')
    expect(handleAt(card.bbox, 104, 400, tol)).toBe('sw')
    expect(handleAt(card.bbox, 300, 98, tol)).toBe('n') // anywhere along an edge
    expect(handleAt(card.bbox, 300, 405, tol)).toBe('s')
    expect(handleAt(card.bbox, 95, 250, tol)).toBe('w')
    expect(handleAt(card.bbox, 501, 120, tol)).toBe('e')
  })

  it('finds nothing inside the box or away from it', () => {
    expect(handleAt(card.bbox, 300, 250, tol)).toBeNull()
    expect(handleAt(card.bbox, 300, 90, tol)).toBeNull()
    expect(handleAt(card.bbox, 520, 250, tol)).toBeNull()
    expect(handleAt(card.bbox, 100, 420, tol)).toBeNull() // below the corner, off the edge
  })

  it('keeps corners reachable on tiny boxes', () => {
    expect(handleAt([10, 10, 4, 4], 14, 14, tol)).toBe('se')
  })
})

describe('resizeBBox', () => {
  const page = { width: 1920, height: 5000 }

  it('moves only the edges the handle owns', () => {
    expect(resizeBBox(card.bbox, 'e', 50, 999, page)).toEqual([100, 100, 450, 300])
    expect(resizeBBox(card.bbox, 'n', 999, -20, page)).toEqual([100, 80, 400, 320])
    expect(resizeBBox(card.bbox, 'sw', -10, 30, page)).toEqual([90, 100, 410, 330])
    expect(resizeBBox(card.bbox, 'ne', 25.25, 10, page)).toEqual([100, 110, 425.3, 290])
  })

  it('stops at the opposite edge instead of flipping', () => {
    expect(resizeBBox(card.bbox, 'w', 1000, 0, page)).toEqual([500 - MIN_BOX_SIZE, 100, MIN_BOX_SIZE, 300])
    expect(resizeBBox(card.bbox, 's', 0, -1000, page)).toEqual([100, 100, 400, MIN_BOX_SIZE])
  })

  it('stays on the page', () => {
    expect(resizeBBox(card.bbox, 'nw', -500, -500, page)).toEqual([0, 0, 500, 400])
    expect(resizeBBox(card.bbox, 'se', 5000, 9000, page)).toEqual([100, 100, 1820, 4900])
  })
})

describe('clampMove and translate', () => {
  const page = { width: 1920, height: 5000 }

  it('moves freely inside the page', () => {
    expect(clampMove([card.bbox, link.bbox], 30, -40, page)).toEqual([30, -40])
    expect(translate(card.bbox, 30.04, -40)).toEqual([130, 60, 400, 300])
  })

  it('stops the whole group at the page edges', () => {
    // The card's left edge (x 100) can go 100 px left; the far box's bottom has 2950 px.
    expect(clampMove([card.bbox, far.bbox], -500, 9000, page)).toEqual([-100, 2950])
    expect(clampMove([card.bbox, far.bbox], 9000, -9000, page)).toEqual([870, -100])
  })
})
