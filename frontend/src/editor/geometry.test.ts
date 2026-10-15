import { describe, expect, it } from 'vitest'

import type { BBox } from '../canvas/geometry'
import { MIN_BOX_SIZE, boxesInRect, hitTest, rectFromDrag } from './geometry'

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
