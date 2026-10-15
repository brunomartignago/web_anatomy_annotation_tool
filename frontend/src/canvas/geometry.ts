// Pure canvas geometry: which strips and boxes are in view, and how zoom moves the view.
// "Page px" = screenshot pixels; "screen px" = page px × zoom.

export type BBox = [number, number, number, number] // [x, y, w, h], top-left origin
export type Completeness = 'empty' | 'partial' | 'complete'

// Below 0.2 so many 2048-px strips would be on screen at once that decoded images alone
// could pass the 500 MB budget on very tall pages (91,086 px = 45 strips).
export const MIN_ZOOM = 0.2
export const MAX_ZOOM = 4
export const ZOOM_STEP = 1.25 // `+` / `-`

export function clampZoom(zoom: number): number {
  return Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, zoom))
}

export function fitWidthZoom(containerWidth: number, pageWidth: number): number {
  return clampZoom(containerWidth / pageWidth)
}

/** Ctrl+wheel: a smooth exponential factor, symmetric for up and down. */
export function wheelZoomFactor(deltaY: number): number {
  return Math.exp(-deltaY * 0.002)
}

/** Strip indices whose rows overlap the viewport (plus `overscanPx` above and below). */
export function visibleStrips(args: {
  scrollTop: number
  viewportHeight: number
  zoom: number
  stripHeight: number
  count: number
  overscanPx: number
}): number[] {
  const { scrollTop, viewportHeight, zoom, stripHeight, count, overscanPx } = args
  const screenStrip = stripHeight * zoom
  const top = Math.max(0, scrollTop - overscanPx)
  const bottom = scrollTop + viewportHeight + overscanPx
  const first = Math.floor(top / screenStrip)
  const last = Math.min(count - 1, Math.ceil(bottom / screenStrip) - 1)
  const strips: number[] = []
  for (let n = first; n <= last; n++) strips.push(n)
  return strips
}

/** New scroll position after a zoom change, keeping the page point under the anchor still. */
export function zoomAround(args: {
  zoom: number
  newZoom: number
  scrollLeft: number
  scrollTop: number
  anchorX: number // relative to the scroll container's visible area
  anchorY: number
}): { scrollLeft: number; scrollTop: number } {
  const { zoom, newZoom, scrollLeft, scrollTop, anchorX, anchorY } = args
  const pageX = (scrollLeft + anchorX) / zoom
  const pageY = (scrollTop + anchorY) / zoom
  return {
    scrollLeft: Math.max(0, pageX * newZoom - anchorX),
    scrollTop: Math.max(0, pageY * newZoom - anchorY),
  }
}

/** Indices of boxes overlapping page rows `top`..`bottom`. */
export function boxesInView(boxes: { bbox: BBox }[], top: number, bottom: number): number[] {
  const hits: number[] = []
  boxes.forEach((box, i) => {
    const [, y, , h] = box.bbox
    if (y < bottom && y + h > top) hits.push(i)
  })
  return hits
}

/** How many of the taxonomy's attributes a box has a value for. */
export function completeness(
  labels: Record<string, string>,
  attributeIds: string[],
): Completeness {
  const done = attributeIds.filter((id) => labels[id]).length
  if (done === 0) return 'empty'
  return done === attributeIds.length ? 'complete' : 'partial'
}

// Same palette as the legacy tool, so the colors keep their meaning.
const COLORS = {
  empty: '#f05252',
  partial: '#fbbf24',
  complete: '#34d399',
  selected: '#4f8ef7',
} as const

export function boxColor(state: Completeness, selected: boolean): string {
  return selected ? COLORS.selected : COLORS[state]
}

// Containers aren't work to label, so they don't use the completeness colors.
const CONTAINER_COLORS = { section: '#a78bfa', component: '#fb923c' }

/** Stroke for a section or component box (dashed in the canvas). */
export function containerColor(kind: 'section' | 'component' | 'element', selected: boolean): string {
  if (selected) return COLORS.selected
  return kind === 'component' ? CONTAINER_COLORS.component : CONTAINER_COLORS.section
}
