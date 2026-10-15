// Pure editing geometry, in page px: hit testing, rubber-band selection, drawing.

import type { BBox } from '../canvas/geometry'

/** Smallest box a drag creates, in page px (the legacy tool ignored drags under 4 px). */
export const MIN_BOX_SIZE = 4

interface Boxed {
  id: string
  bbox: BBox
}

const area = ([, , w, h]: BBox) => w * h

const contains = ([x, y, w, h]: BBox, px: number, py: number) =>
  px >= x && px <= x + w && py >= y && py <= y + h

/** The smallest box containing the point, so a link inside a card wins over the card. */
export function hitTest(boxes: Boxed[], px: number, py: number): string | null {
  let best: Boxed | null = null
  for (const box of boxes) {
    if (contains(box.bbox, px, py) && (!best || area(box.bbox) < area(best.bbox))) best = box
  }
  return best?.id ?? null
}

/** Ids of the boxes a rubber-band rectangle touches, in file order. */
export function boxesInRect(boxes: Boxed[], [rx, ry, rw, rh]: BBox): string[] {
  return boxes
    .filter(({ bbox: [x, y, w, h] }) => x <= rx + rw && x + w >= rx && y <= ry + rh && y + h >= ry)
    .map((box) => box.id)
}

const round = (v: number) => Math.round(v * 10) / 10

/** The box a drag from `a` to `b` draws: normalized, clamped to the page, or null if tiny. */
export function rectFromDrag(
  a: { x: number; y: number },
  b: { x: number; y: number },
  page: { width: number; height: number },
): BBox | null {
  const clampX = (v: number) => Math.min(page.width, Math.max(0, v))
  const clampY = (v: number) => Math.min(page.height, Math.max(0, v))
  const left = clampX(Math.min(a.x, b.x))
  const right = clampX(Math.max(a.x, b.x))
  const top = clampY(Math.min(a.y, b.y))
  const bottom = clampY(Math.max(a.y, b.y))
  if (right - left < MIN_BOX_SIZE || bottom - top < MIN_BOX_SIZE) return null
  return [round(left), round(top), round(right - left), round(bottom - top)]
}
