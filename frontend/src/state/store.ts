import { produce } from 'immer'
import { create } from 'zustand'
import { immer } from 'zustand/middleware/immer'

import type { Annotation, PageAnnotationFileV1 } from '../api/annotation'
import type { PageResponse, PageSummary, Progress, Taxonomy } from '../api/types'
import type { BBox } from '../canvas/geometry'
import { clampZoom } from '../canvas/geometry'
import { countAction } from '../editor/effort'
import { similarBoxes } from '../editor/geometry'
import { edit, emptyHistory, redo as redoStep, undo as undoStep } from '../editor/history'
import type { History } from '../editor/history'
import { newUlid } from '../editor/ids'
import { applyInheritance } from '../editor/inheritance'
import type { KeymapPreset } from '../keyboard/keymap'
import { applyLabel } from '../panels/labels'

export type LoadStatus = 'idle' | 'loading' | 'ready' | 'error'
/** draw: element boxes · section: template-section boxes (Shift+D) · select. */
export type Tool = 'draw' | 'section' | 'select'
export type BoxKind = Annotation['kind']
/** saved: on disk · pending: edited, waiting for autosave · conflict: changed elsewhere. */
export type SaveState = 'saved' | 'pending' | 'saving' | 'error' | 'conflict'
export type SelectMode = 'replace' | 'add' | 'toggle'

export interface AppState {
  status: LoadStatus
  error: string | null
  taxonomy: Taxonomy | null
  project: string | null
  pages: PageSummary[]
  currentPageId: string | null

  /** The open page, once loaded, and which page id it belongs to. */
  page: PageResponse | null
  pageId: string | null
  pageStatus: LoadStatus
  pageError: string | null
  zoom: number

  // Editing
  tool: Tool
  selectedIds: string[]
  history: History
  /** Bumped by every change to the annotations, undo/redo included; autosave watches it. */
  docVersion: number
  savedVersion: number
  saveState: SaveState
  saveError: string | null
  /** A request for the canvas to scroll a box into view (the nonce repeats requests). */
  focus: { id: string; nonce: number } | null
  /** Attribute whose keyboard picker is open (its hotkey was pressed), if any. */
  picker: string | null
  cheatSheet: boolean
  palette: boolean
  /** The preset being painted with (3.5): each clicked box gets it. Null when not painting. */
  paint: KeymapPreset | null

  startLoading: () => void
  loaded: (taxonomy: Taxonomy, project: string, pages: PageSummary[]) => void
  failed: (message: string) => void
  openPage: (pageId: string) => void
  /** Move through the page queue (`]` / `[` in 2.5); stops at the ends. */
  stepPage: (delta: 1 | -1) => void

  pageLoading: () => void
  pageLoaded: (pageId: string, page: PageResponse) => void
  pageFailed: (message: string) => void
  setZoom: (zoom: number) => void

  setTool: (tool: Tool) => void
  select: (ids: string[], mode?: SelectMode) => void
  /** Grow the selection to similar boxes: same size, same row or column (Shift+A, 3.6a). */
  selectSimilar: () => void
  addBox: (bbox: BBox, kind?: BoxKind) => string | null
  /** Make the selected boxes elements, sections or components (one undo step). */
  setKind: (kind: BoxKind) => void
  /** Move or resize boxes (id → new bbox) as one undo step; inheritance follows. */
  setBBoxes: (changes: Record<string, BBox>) => void
  deleteSelected: () => void
  /** Set (or with null, remove) one attribute on every selected box, as one undo step. */
  setLabel: (attrId: string, value: string | null) => void
  /** Set several attributes at once (a preset) on every selected box, as one undo step. */
  applyPreset: (labels: Record<string, string>) => void
  /** Start painting with a preset, or stop (null). */
  setPaint: (preset: KeymapPreset | null) => void
  /** Apply the paint preset to these boxes and select them, as one undo step. */
  paintBoxes: (ids: string[]) => void
  focusBox: (id: string) => void
  setPicker: (attributeId: string | null) => void
  setCheatSheet: (open: boolean) => void
  setPalette: (open: boolean) => void
  undo: () => void
  redo: () => void

  saveStarted: () => void
  saveSucceeded: (pageId: string, version: number, etag: string, progress: Progress) => void
  saveFailed: (message: string) => void
  saveConflict: (message: string) => void
}

const editingReset = {
  selectedIds: [] as string[],
  history: emptyHistory(),
  docVersion: 0,
  savedVersion: 0,
  saveState: 'saved' as SaveState,
  saveError: null,
  focus: null as { id: string; nonce: number } | null,
}

export const initialState = {
  status: 'idle' as LoadStatus,
  error: null,
  taxonomy: null,
  project: null,
  pages: [],
  currentPageId: null,
  page: null,
  pageId: null,
  pageStatus: 'idle' as LoadStatus,
  pageError: null,
  zoom: 1,
  tool: 'draw' as Tool,
  picker: null as string | null,
  cheatSheet: false,
  palette: false,
  paint: null as KeymapPreset | null,
  ...editingReset,
}

/** After an edit: autosave should run, unless the file changed elsewhere (keep the warning). */
function markEdited(s: { saveState: SaveState }) {
  if (s.saveState !== 'conflict') s.saveState = 'pending'
}

export const useAppStore = create<AppState>()(
  immer((set, get) => {
    /**
     * Apply an edit to the open page's annotations, recording it for undo. Inherited labels
     * are recomputed in the same step, so a section relabel and its children are one undo.
     */
    const editDoc = (recipe: (doc: PageAnnotationFileV1) => void, selectAfter?: string[]) => {
      const { page, history, taxonomy } = get()
      if (!page) return
      const inheritable = (taxonomy?.attributes ?? [])
        .filter((a) => a.inherit_from_parent)
        .map((a) => a.id)
      const result = edit(page.annotations, history, (doc) => {
        recipe(doc)
        if (inheritable.length > 0) applyInheritance(doc, inheritable)
      })
      if (result.history === history) return // nothing changed
      // Counted outside the undo step, so undoing can't lower the count.
      const counted = produce(result.doc, countAction)
      set((s) => {
        s.page!.annotations = counted
        s.history = result.history
        s.docVersion += 1
        markEdited(s)
        if (selectAfter) s.selectedIds = selectAfter
      })
    }

    /** Set every attribute a preset names on these boxes, as one undo step. */
    const applyPresetTo = (
      ids: string[],
      labels: Record<string, string>,
      selectAfter?: string[],
    ) => {
      const chosen = new Set(ids)
      if (chosen.size === 0) return
      const now = new Date().toISOString()
      editDoc((doc) => {
        for (const box of doc.annotations) {
          if (!chosen.has(box.id)) continue
          for (const [attrId, value] of Object.entries(labels)) {
            applyLabel(box, attrId, value, now)
          }
        }
      }, selectAfter)
    }

    const step = (fn: typeof undoStep) => {
      const { page, history } = get()
      if (!page) return
      const result = fn(page.annotations, history)
      if (!result) return
      const counted = produce(result.doc, countAction) // undo and redo are effort too
      set((s) => {
        s.page!.annotations = counted
        s.history = result.history
        s.docVersion += 1
        markEdited(s)
        const ids = new Set(result.doc.annotations.map((a) => a.id))
        s.selectedIds = s.selectedIds.filter((id) => ids.has(id))
      })
    }

    return {
      ...initialState,

      startLoading: () =>
        set((s) => {
          s.status = 'loading'
          s.error = null
        }),

      loaded: (taxonomy, project, pages) =>
        set((s) => {
          s.status = 'ready'
          s.taxonomy = taxonomy
          s.project = project
          s.pages = pages
          const stillThere = pages.some((p) => p.id === s.currentPageId)
          if (!stillThere) s.currentPageId = pages[0]?.id ?? null
        }),

      failed: (message) =>
        set((s) => {
          s.status = 'error'
          s.error = message
        }),

      openPage: (pageId) =>
        set((s) => {
          if (s.pages.some((p) => p.id === pageId)) s.currentPageId = pageId
        }),

      stepPage: (delta) =>
        set((s) => {
          const index = s.pages.findIndex((p) => p.id === s.currentPageId)
          const next = s.pages[index + delta]
          if (index >= 0 && next) s.currentPageId = next.id
        }),

      pageLoading: () =>
        set((s) => {
          s.pageStatus = 'loading'
          s.pageError = null
        }),

      pageLoaded: (pageId, page) =>
        set((s) => {
          s.page = page
          s.pageId = pageId
          s.pageStatus = 'ready'
          s.picker = null
          Object.assign(s, editingReset, { history: emptyHistory() })
        }),

      pageFailed: (message) =>
        set((s) => {
          s.page = null
          s.pageId = null
          s.pageStatus = 'error'
          s.pageError = message
        }),

      setZoom: (zoom) =>
        set((s) => {
          s.zoom = clampZoom(zoom)
        }),

      setTool: (tool) =>
        set((s) => {
          s.tool = tool
          s.paint = null // picking a tool ends painting
        }),

      select: (ids, mode = 'replace') =>
        set((s) => {
          if (mode === 'replace') {
            s.selectedIds = [...new Set(ids)]
          } else if (mode === 'add') {
            s.selectedIds = [...new Set([...s.selectedIds, ...ids])]
          } else {
            const current = new Set(s.selectedIds)
            for (const id of ids) {
              if (current.has(id)) current.delete(id)
              else current.add(id)
            }
            s.selectedIds = [...current]
          }
        }),

      selectSimilar: () =>
        set((s) => {
          if (!s.page || s.selectedIds.length === 0) return
          s.selectedIds = similarBoxes(s.page.annotations.annotations, s.selectedIds)
        }),

      addBox: (bbox, kind = 'element') => {
        if (!get().page) return null
        const box: Annotation = {
          id: newUlid(),
          kind,
          bbox,
          labels: {},
          source: 'human',
          status: 'accepted',
          created_at: new Date().toISOString(),
        }
        editDoc((doc) => {
          doc.annotations.push(box)
        }, [box.id])
        return box.id
      },

      setKind: (kind) => {
        const selected = new Set(get().selectedIds)
        if (selected.size === 0) return
        const now = new Date().toISOString()
        editDoc((doc) => {
          for (const box of doc.annotations) {
            if (selected.has(box.id) && box.kind !== kind) {
              box.kind = kind
              box.updated_at = now
            }
          }
        })
      },

      setBBoxes: (changes) => {
        const now = new Date().toISOString()
        editDoc((doc) => {
          for (const box of doc.annotations) {
            const bbox = changes[box.id]
            if (!bbox || bbox.every((v, i) => v === box.bbox[i])) continue
            box.bbox = bbox
            // Like a relabel: a moved legacy or machine box is now a corrected one.
            if (box.source !== 'human' || box.status === 'suggested') box.status = 'edited'
            box.updated_at = now
          }
        })
      },

      deleteSelected: () => {
        const selected = new Set(get().selectedIds)
        if (selected.size === 0) return
        editDoc((doc) => {
          doc.annotations = doc.annotations.filter((a) => !selected.has(a.id))
        }, [])
      },

      setLabel: (attrId, value) => {
        const selected = new Set(get().selectedIds)
        if (selected.size === 0) return
        const now = new Date().toISOString()
        editDoc((doc) => {
          for (const box of doc.annotations) {
            if (selected.has(box.id)) applyLabel(box, attrId, value, now)
          }
        })
      },

      applyPreset: (labels) => applyPresetTo(get().selectedIds, labels),

      setPaint: (preset) =>
        set((s) => {
          s.paint = preset
        }),

      paintBoxes: (ids) => {
        const { paint } = get()
        if (!paint || ids.length === 0) return
        applyPresetTo(ids, paint.labels, ids)
      },

      focusBox: (id) =>
        set((s) => {
          s.focus = { id, nonce: (s.focus?.nonce ?? 0) + 1 }
        }),

      setPicker: (attributeId) =>
        set((s) => {
          s.picker = attributeId
        }),

      setCheatSheet: (open) =>
        set((s) => {
          s.cheatSheet = open
        }),

      setPalette: (open) =>
        set((s) => {
          s.palette = open
          if (open) s.picker = null
        }),

      undo: () => step(undoStep),
      redo: () => step(redoStep),

      saveStarted: () =>
        set((s) => {
          s.saveState = 'saving'
          s.saveError = null
        }),

      saveSucceeded: (pageId, version, etag, progress) =>
        set((s) => {
          const row = s.pages.find((p) => p.id === pageId)
          if (row) {
            row.progress = progress
            row.has_annotations = true
          }
          if (s.pageId !== pageId || !s.page) return // the user has moved to another page
          s.page.etag = etag
          s.savedVersion = Math.max(s.savedVersion, version)
          s.saveState = s.savedVersion === s.docVersion ? 'saved' : 'pending'
        }),

      saveFailed: (message) =>
        set((s) => {
          s.saveState = 'error'
          s.saveError = message
        }),

      saveConflict: (message) =>
        set((s) => {
          s.saveState = 'conflict'
          s.saveError = message
        }),
    }
  }),
)
