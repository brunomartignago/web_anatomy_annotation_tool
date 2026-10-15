import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import type { MouseEvent, PointerEvent } from 'react'
import { useShallow } from 'zustand/react/shallow'

import { stripUrl } from '../api/client'
import type { PageResponse } from '../api/types'
import { boxesInRect, hitTest, rectFromDrag } from '../editor/geometry'
import { useAppStore } from '../state/store'
import type { SaveState } from '../state/store'
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
import type { BBox } from './geometry'

// Screen px of page kept mounted above and below the viewport, so strips are ready
// before they scroll into view. Strips further away are unmounted, which lets the browser
// drop their decoded pixels: that's what keeps a 91,086 px page under the memory budget.
const OVERSCAN_PX = 800
/** A press that moves less than this (screen px) is a click, not a drag. */
const CLICK_SLOP_PX = 4

interface StageProps {
  project: string
  pageId: string
  page: PageResponse
  attributeIds: string[]
}

type Gesture =
  | { kind: 'pan'; x: number; y: number; left: number; top: number }
  | { kind: 'draw' | 'select'; x: number; y: number; start: Point; shift: boolean }

interface Point {
  x: number
  y: number
}

const SAVE_LABELS: Record<SaveState, string> = {
  saved: 'Saved',
  pending: 'Unsaved changes…',
  saving: 'Saving…',
  error: 'Not saved',
  conflict: 'Not saved: changed elsewhere',
}

/** The page canvas: lazy-loaded strips, boxes on top, zoom, pan, draw and select. */
export function Stage({ project, pageId, page, attributeIds }: StageProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const worldRef = useRef<HTMLDivElement>(null)
  const { zoom, tool, selectedIds, saveState, saveError } = useAppStore(
    useShallow((s) => ({
      zoom: s.zoom,
      tool: s.tool,
      selectedIds: s.selectedIds,
      saveState: s.saveState,
      saveError: s.saveError,
    })),
  )
  const { setZoom, setTool, select, addBox, deleteSelected, undo, redo } = useAppStore.getState()
  const [view, setView] = useState({ scrollTop: 0, height: 0 })
  const [gestureKind, setGestureKind] = useState<Gesture['kind'] | null>(null)
  const [preview, setPreview] = useState<BBox | null>(null)
  const pendingScroll = useRef<{ scrollLeft: number; scrollTop: number } | null>(null)
  const gesture = useRef<Gesture | null>(null)
  const spaceDown = useRef(false)

  const { width: pageWidth, height: pageHeight } = page.annotations.page
  const stripHeight = page.strips.height
  const boxes = page.annotations.annotations
  const selected = useMemo(() => new Set(selectedIds), [selectedIds])

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

  const cancelGesture = useCallback(() => {
    gesture.current = null
    setGestureKind(null)
    setPreview(null)
  }, [])

  // View: + / - / Ctrl+0, Space to pan. Editing: D / S, Delete / X, Esc, Ctrl+Z / Ctrl+Y.
  useEffect(() => {
    const isTyping = (target: EventTarget | null) =>
      target instanceof HTMLElement &&
      (target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName))

    const onKeyDown = (event: KeyboardEvent) => {
      if (isTyping(event.target)) return
      const el = containerRef.current
      const zoomNow = useAppStore.getState().zoom
      const modifier = event.ctrlKey || event.metaKey
      const key = event.key.toLowerCase()
      if (modifier && key === '0') {
        event.preventDefault()
        if (el) zoomTo(fitWidthZoom(el.clientWidth, pageWidth), 0)
      } else if (modifier && key === 'z') {
        event.preventDefault()
        if (event.shiftKey) redo()
        else undo()
      } else if (modifier && key === 'y') {
        event.preventDefault()
        redo()
      } else if (modifier || event.altKey) {
        return // leave other shortcuts (copy, reload…) to the browser
      } else if (key === '+' || key === '=') {
        event.preventDefault()
        zoomTo(zoomNow * ZOOM_STEP)
      } else if (key === '-' || key === '_') {
        event.preventDefault()
        zoomTo(zoomNow / ZOOM_STEP)
      } else if (key === 'd') {
        setTool('draw')
      } else if (key === 's') {
        setTool('select')
      } else if (key === 'delete' || key === 'backspace' || key === 'x') {
        event.preventDefault()
        deleteSelected()
      } else if (key === 'escape') {
        if (gesture.current) cancelGesture()
        else select([])
      } else if (key === ' ' && !(event.target instanceof HTMLButtonElement)) {
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
  }, [zoomTo, pageWidth, setTool, deleteSelected, select, undo, redo, cancelGesture])

  /** Pointer position in page px. */
  const toPage = (event: PointerEvent<HTMLDivElement>): Point => {
    const rect = worldRef.current?.getBoundingClientRect()
    const z = useAppStore.getState().zoom
    return { x: (event.clientX - (rect?.left ?? 0)) / z, y: (event.clientY - (rect?.top ?? 0)) / z }
  }

  const onPointerDown = (event: PointerEvent<HTMLDivElement>) => {
    const el = containerRef.current
    if (!el) return
    const wantsPan = event.button === 1 || (event.button === 0 && spaceDown.current)
    if (wantsPan) {
      event.preventDefault()
      gesture.current = {
        kind: 'pan',
        x: event.clientX,
        y: event.clientY,
        left: el.scrollLeft,
        top: el.scrollTop,
      }
    } else if (event.button === 0) {
      gesture.current = {
        kind: tool,
        x: event.clientX,
        y: event.clientY,
        start: toPage(event),
        shift: event.shiftKey,
      }
    } else {
      return
    }
    el.setPointerCapture?.(event.pointerId)
    setGestureKind(gesture.current.kind)
  }

  const onPointerMove = (event: PointerEvent<HTMLDivElement>) => {
    const el = containerRef.current
    const g = gesture.current
    if (!el || !g) return
    if (g.kind === 'pan') {
      el.scrollLeft = g.left - (event.clientX - g.x)
      el.scrollTop = g.top - (event.clientY - g.y)
      return
    }
    const moved = Math.hypot(event.clientX - g.x, event.clientY - g.y) >= CLICK_SLOP_PX
    setPreview(moved ? rectFromDrag(g.start, toPage(event), page.annotations.page) : null)
  }

  const onPointerUp = (event: PointerEvent<HTMLDivElement>) => {
    const g = gesture.current
    if (!g) return
    containerRef.current?.releasePointerCapture?.(event.pointerId)
    cancelGesture()
    if (g.kind === 'pan') return

    const end = toPage(event)
    const isClick = Math.hypot(event.clientX - g.x, event.clientY - g.y) < CLICK_SLOP_PX
    if (g.kind === 'draw') {
      const bbox = rectFromDrag(g.start, end, page.annotations.page)
      if (bbox) addBox(bbox)
    } else if (isClick) {
      const hit = hitTest(boxes, end.x, end.y)
      if (g.shift) {
        if (hit) select([hit], 'toggle')
      } else {
        select(hit ? [hit] : [])
      }
    } else {
      const rect = rectFromDrag(g.start, end, page.annotations.page)
      const ids = rect ? boxesInRect(boxes, rect) : []
      select(ids, g.shift ? 'add' : 'replace')
    }
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

  const viewportClass = [
    'stage__viewport',
    gestureKind === 'pan' && 'is-panning',
    tool === 'draw' && 'is-drawing',
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <div className="stage">
      <div
        ref={containerRef}
        className={viewportClass}
        aria-label="Page canvas"
        onScroll={readView}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={cancelGesture}
        onMouseDown={onMouseDown}
      >
        <div
          ref={worldRef}
          className="stage__world"
          style={{ width: pageWidth * zoom, height: pageHeight * zoom }}
        >
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
              const isSelected = selected.has(box.id)
              const color = boxColor(completeness(box.labels, attributeIds), isSelected)
              const tag = String(i + 1)
              return (
                <g key={box.id} data-box-id={box.id} data-selected={isSelected || undefined}>
                  <rect
                    x={x * zoom}
                    y={y * zoom}
                    width={w * zoom}
                    height={h * zoom}
                    fill={isSelected ? 'rgba(79, 142, 247, 0.12)' : 'none'}
                    stroke={color}
                    strokeWidth={isSelected ? 3 : 2}
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
            {preview && (
              <rect
                className={gestureKind === 'draw' ? 'stage__draft' : 'stage__band'}
                x={preview[0] * zoom}
                y={preview[1] * zoom}
                width={preview[2] * zoom}
                height={preview[3] * zoom}
              />
            )}
          </svg>
        </div>
      </div>
      <div className="stage__status" role="status">
        <span>
          {Math.round(zoom * 100)}% · {boxes.length} boxes · {pageWidth}×{pageHeight} px
        </span>
        <span className="stage__tool">
          {tool === 'draw' ? 'Draw (D)' : 'Select (S)'}
          {selectedIds.length > 0 && ` · ${selectedIds.length} selected`}
        </span>
        <span className={`stage__save stage__save--${saveState}`} title={saveError ?? undefined}>
          {SAVE_LABELS[saveState]}
        </span>
      </div>
    </div>
  )
}
