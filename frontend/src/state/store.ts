import { create } from 'zustand'
import { immer } from 'zustand/middleware/immer'

import type { PageSummary, Taxonomy } from '../api/types'

// App-wide state. Annotation editing (boxes, undo/redo via immer patches) is added in 2.4.

export type LoadStatus = 'idle' | 'loading' | 'ready' | 'error'

export interface AppState {
  status: LoadStatus
  error: string | null
  taxonomy: Taxonomy | null
  project: string | null
  pages: PageSummary[]
  currentPageId: string | null

  startLoading: () => void
  loaded: (taxonomy: Taxonomy, project: string, pages: PageSummary[]) => void
  failed: (message: string) => void
  openPage: (pageId: string) => void
  /** Move through the page queue (`]` / `[` in 2.5); stops at the ends. */
  stepPage: (delta: 1 | -1) => void
}

export const initialState = {
  status: 'idle' as LoadStatus,
  error: null,
  taxonomy: null,
  project: null,
  pages: [],
  currentPageId: null,
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
  })),
)
