import { useEffect } from 'react'
import { useShallow } from 'zustand/react/shallow'

import { ApiError, api } from '../api/client'
import { useAppStore } from '../state/store'

/** Save this long after the last edit, so a burst of edits becomes one write. */
export const AUTOSAVE_DELAY_MS = 800

/**
 * Save the open page now, if it has unsaved edits. Sends the ETag from the last load or save,
 * so a file changed elsewhere (another tab, a script) is never overwritten: the server answers
 * 412 and autosave stops until the page is reloaded.
 */
export async function saveNow(): Promise<void> {
  const s = useAppStore.getState()
  const { page, project, pageId, docVersion, savedVersion, saveState } = s
  if (!page || !project || !pageId) return
  if (docVersion === savedVersion || saveState === 'saving' || saveState === 'conflict') return

  s.saveStarted()
  try {
    const result = await api.save(project, pageId, page.annotations, page.etag)
    useAppStore.getState().saveSucceeded(pageId, docVersion, result.etag, result.progress)
  } catch (exc) {
    const message = exc instanceof Error ? exc.message : String(exc)
    if (exc instanceof ApiError && exc.status === 412) {
      useAppStore.getState().saveConflict(message)
    } else {
      useAppStore.getState().saveFailed(message)
    }
  }
}

/** Debounced autosave of the open page, plus a warning before closing with unsaved edits. */
export function useAutosave(): void {
  const { pageId, docVersion, savedVersion, saveState } = useAppStore(
    useShallow((s) => ({
      pageId: s.pageId,
      docVersion: s.docVersion,
      savedVersion: s.savedVersion,
      saveState: s.saveState,
    })),
  )

  useEffect(() => {
    if (!pageId || docVersion === savedVersion) return
    if (saveState === 'saving' || saveState === 'conflict') return
    const timer = setTimeout(() => void saveNow(), AUTOSAVE_DELAY_MS)
    return () => clearTimeout(timer)
  }, [pageId, docVersion, savedVersion, saveState])

  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => {
      const s = useAppStore.getState()
      if (s.docVersion !== s.savedVersion) event.preventDefault()
    }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [])
}
