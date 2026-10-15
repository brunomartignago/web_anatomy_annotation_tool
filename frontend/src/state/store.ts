import { create } from 'zustand'
import { immer } from 'zustand/middleware/immer'

import type { PageResponse, PageSummary, Taxonomy } from '../api/types'
import { clampZoom } from '../canvas/geometry'

// App-wide state. Annotation editing (draw/select, undo/redo via immer patches) is 2.4.

export type LoadStatus = 'idle' | 'loading' | 'ready' | 'error'

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
  selectedIds: string[]

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
  selectedIds: [],
}

export const useAppStore = create<AppState>()(
  immer((set) => ({
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
        s.selectedIds = []
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
  })),
)
