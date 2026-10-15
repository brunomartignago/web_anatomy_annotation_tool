import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import type { MouseEvent, PointerEvent } from 'react'

import { stripUrl } from '../api/client'
import type { PageResponse } from '../api/types'
import { useAppStore } from '../state/store'
import {
  ZOOM_STEP,
  boxColor,
  boxesInView,
  clampZoom,
  completeness,
  fitWidthZoom,
  visibleStrips,
  wheelZoomFactor,
  zoomAround,
} from './geometry'

// Screen px of page kept mounted above and below the viewport, so strips are ready
// before they scroll into view. Strips further away are unmounted, which lets the browser
// drop their decoded pixels: that's what keeps a 91,086 px page under the memory budget.
const OVERSCAN_PX = 800

interface StageProps {
  project: string
  pageId: string
  page: PageResponse
  attributeIds: string[]
}

/** The page canvas: lazy-loaded strips, boxes on top, zoom and pan. Native scrolling. */
export function Stage({ project, pageId, page, attributeIds }: StageProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const zoom = useAppStore((s) => s.zoom)
  const setZoom = useAppStore((s) => s.setZoom)
  const selectedIds = useAppStore((s) => s.selectedIds)
  const [view, setView] = useState({ scrollTop: 0, height: 0 })
  const [panning, setPanning] = useState(false)
  const pendingScroll = useRef<{ scrollLeft: number; scrollTop: number } | null>(null)
  const panStart = useRef<{ x: number; y: number; left: number; top: number } | null>(null)
  const spaceDown = useRef(false)

  const { width: pageWidth, height: pageHeight } = page.annotations.page
  const stripHeight = page.strips.height
  const boxes = page.annotations.annotations

  const readView = useCallback(() => {
    const el = containerRef.current
    if (el) setView({ scrollTop: el.scrollTop, height: el.clientHeight })
  }, [])

  // A newly opened page starts at the top, fitted to the width.
  useLayoutEffect(() => {
    const el = containerRef.current
    if (!el) return
    setZoom(fitWidthZoom(el.clientWidth || pageWidth, pageWidth))
    el.scrollTop = 0
    el.scrollLeft = 0
    readView()
  }, [pageId, pageWidth, setZoom, readView])

  useEffect(() => {
    const el = containerRef.current
    if (!el || typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(readView)
    observer.observe(el)
    return () => observer.disconnect()
  }, [readView])

  // After a zoom change has resized the world, restore the scroll position zoomAround chose.
  useLayoutEffect(() => {
    const el = containerRef.current
    const target = pendingScroll.current
    if (!el || !target) return
    el.scrollLeft = target.scrollLeft
    el.scrollTop = target.scrollTop
    pendingScroll.current = null
    readView()
  }, [zoom, readView])

  /** Zoom to `newZoom`, keeping the page point under (anchorX, anchorY) still. */
  const zoomTo = useCallback(
    (newZoom: number, anchorX?: number, anchorY?: number) => {
      const el = containerRef.current
      const current = useAppStore.getState().zoom
      const next = clampZoom(newZoom)
      if (!el || next === current) return
      pendingScroll.current = zoomAround({
        zoom: current,
        newZoom: next,
        scrollLeft: el.scrollLeft,
        scrollTop: el.scrollTop,
        anchorX: anchorX ?? el.clientWidth / 2,
        anchorY: anchorY ?? el.clientHeight / 2,
      })
      setZoom(next)
    },
    [setZoom],
  )

  // Ctrl+wheel zooms around the cursor. React's onWheel is passive, so attach it directly.
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const onWheel = (event: WheelEvent) => {
      if (!event.ctrlKey) return
      event.preventDefault()
      const rect = el.getBoundingClientRect()
      const zoomNow = useAppStore.getState().zoom
      zoomTo(
        zoomNow * wheelZoomFactor(event.deltaY),
        event.clientX - rect.left,
        event.clientY - rect.top,
      )
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [zoomTo])

  // `+` / `-` zoom, Ctrl+0 fits the width, holding Space turns dragging into panning.
  useEffect(() => {
    const isTyping = (target: EventTarget | null) =>
      target instanceof HTMLElement &&
      (target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName))

    const onKeyDown = (event: KeyboardEvent) => {
      if (isTyping(event.target)) return
      const el = containerRef.current
      const zoomNow = useAppStore.getState().zoom
      const modifier = event.ctrlKey || event.metaKey
      if (modifier && event.key === '0') {
        event.preventDefault()
        if (el) zoomTo(fitWidthZoom(el.clientWidth, pageWidth), 0)
      } else if (!modifier && (event.key === '+' || event.key === '=')) {
        event.preventDefault()
        zoomTo(zoomNow * ZOOM_STEP)
      } else if (!modifier && (event.key === '-' || event.key === '_')) {
        event.preventDefault()
        zoomTo(zoomNow / ZOOM_STEP)
      } else if (event.key === ' ' && !(event.target instanceof HTMLButtonElement)) {
        event.preventDefault() // otherwise Space scrolls the page
        spaceDown.current = true
      }
    }
    const onKeyUp = (event: KeyboardEvent) => {
      if (event.key === ' ') spaceDown.current = false
    }
    window.addEventListener('keydown', onKeyDown)
    window.addEventListener('keyup', onKeyUp)
    return () => {
      window.removeEventListener('keydown', onKeyDown)
      window.removeEventListener('keyup', onKeyUp)
    }
  }, [zoomTo, pageWidth])

  const onPointerDown = (event: PointerEvent<HTMLDivElement>) => {
    const el = containerRef.current
    const wantsPan = event.button === 1 || (event.button === 0 && spaceDown.current)
    if (!el || !wantsPan) return
    event.preventDefault()
    panStart.current = { x: event.clientX, y: event.clientY, left: el.scrollLeft, top: el.scrollTop }
    el.setPointerCapture(event.pointerId)
    setPanning(true)
  }

  const onPointerMove = (event: PointerEvent<HTMLDivElement>) => {
    const el = containerRef.current
    const start = panStart.current
    if (!el || !start) return
    el.scrollLeft = start.left - (event.clientX - start.x)
    el.scrollTop = start.top - (event.clientY - start.y)
  }

  const onPointerUp = (event: PointerEvent<HTMLDivElement>) => {
    if (!panStart.current) return
    panStart.current = null
    containerRef.current?.releasePointerCapture(event.pointerId)
    setPanning(false)
  }

  // Middle-click would otherwise start the browser's autoscroll.
  const onMouseDown = (event: MouseEvent<HTMLDivElement>) => {
    if (event.button === 1) event.preventDefault()
  }

  const strips = visibleStrips({
    scrollTop: view.scrollTop,
    viewportHeight: Math.max(view.height, 1),
    zoom,
    stripHeight,
    count: page.strips.count,
    overscanPx: OVERSCAN_PX,
  })

  const viewTop = (view.scrollTop - OVERSCAN_PX) / zoom
  const viewBottom = (view.scrollTop + view.height + OVERSCAN_PX) / zoom
  const visibleBoxes = useMemo(
    () => boxesInView(boxes, viewTop, viewBottom),
    [boxes, viewTop, viewBottom],
  )

  return (
    <div className="stage">
      <div
        ref={containerRef}
        className={panning ? 'stage__viewport is-panning' : 'stage__viewport'}
        aria-label="Page canvas"
        onScroll={readView}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        onMouseDown={onMouseDown}
      >
        <div className="stage__world" style={{ width: pageWidth * zoom, height: pageHeight * zoom }}>
          {strips.map((n) => {
            const top = n * stripHeight
            const rows = Math.min(stripHeight, pageHeight - top)
            return (
              <img
                key={n}
                className="stage__strip"
                src={stripUrl(project, pageId, n)}
                alt=""
                draggable={false}
                decoding="async"
                style={{ top: top * zoom, width: pageWidth * zoom, height: rows * zoom }}
              />
            )
          })}
          <svg
            className="stage__boxes"
            width={pageWidth * zoom}
            height={pageHeight * zoom}
            role="img"
            aria-label="Boxes"
          >
            {visibleBoxes.map((i) => {
              const box = boxes[i]
              const [x, y, w, h] = box.bbox
              const color = boxColor(
                completeness(box.labels, attributeIds),
                selectedIds.includes(box.id),
              )
              const tag = String(i + 1)
              return (
                <g key={box.id} data-box-id={box.id}>
                  <rect
                    x={x * zoom}
                    y={y * zoom}
                    width={w * zoom}
                    height={h * zoom}
                    fill="none"
                    stroke={color}
                    strokeWidth={2}
                  />
                  <rect
                    x={x * zoom}
                    y={y * zoom}
                    width={tag.length * 7 + 6}
                    height={14}
                    fill={color}
                  />
                  <text x={x * zoom + 3} y={y * zoom + 11} className="stage__tag">
                    {tag}
                  </text>
                </g>
              )
            })}
          </svg>
        </div>
      </div>
      <div className="stage__status" role="status">
        {Math.round(zoom * 100)}% · {boxes.length} boxes · {pageWidth}×{pageHeight} px
      </div>
    </div>
  )
}
