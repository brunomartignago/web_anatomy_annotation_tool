import { useEffect, useMemo } from 'react'
import { useShallow } from 'zustand/react/shallow'

import { api } from './api/client'
import type { PageSummary } from './api/types'
import { Stage } from './canvas/Stage'
import { saveNow, useAutosave } from './editor/autosave'
import { useAppStore } from './state/store'

// The shell: loads the served project, lists its pages and shows the open one on the
// canvas. The label panel and page queue (2.5) plug in here.
export default function App() {
  const {
    status,
    error,
    taxonomy,
    project,
    pages,
    currentPageId,
    page,
    pageStatus,
    pageError,
    saveState,
    saveError,
  } = useAppStore(
    useShallow((s) => ({
      status: s.status,
      error: s.error,
      taxonomy: s.taxonomy,
      project: s.project,
      pages: s.pages,
      currentPageId: s.currentPageId,
      page: s.pageId === s.currentPageId ? s.page : null,
      pageStatus: s.pageStatus,
      pageError: s.pageError,
      saveState: s.saveState,
      saveError: s.saveError,
    })),
  )
  const { startLoading, loaded, failed, openPage, pageLoading, pageLoaded, pageFailed } =
    useAppStore.getState()
  const attributeIds = useMemo(() => taxonomy?.attributes.map((a) => a.id) ?? [], [taxonomy])

  useAutosave()

  /** After a save conflict: drop local edits and load the version on disk. */
  const reloadPage = async () => {
    if (!project || !currentPageId) return
    const ok = window.confirm(
      'This page was changed elsewhere. Reload it from disk? Your unsaved edits on it are lost.',
    )
    if (!ok) return
    try {
      pageLoaded(currentPageId, await api.page(project, currentPageId))
    } catch (exc) {
      pageFailed(exc instanceof Error ? exc.message : String(exc))
    }
  }

  // Open the selected page, saving the one being left first.
  useEffect(() => {
    if (!project || !currentPageId) return
    void saveNow() // reads the old page synchronously, before it is replaced
    let cancelled = false
    pageLoading()
    api.page(project, currentPageId).then(
      (loadedPage) => !cancelled && pageLoaded(currentPageId, loadedPage),
      (exc: unknown) => !cancelled && pageFailed(exc instanceof Error ? exc.message : String(exc)),
    )
    return () => {
      cancelled = true
    }
  }, [project, currentPageId, pageLoading, pageLoaded, pageFailed])

  useEffect(() => {
    let cancelled = false
    startLoading()
    ;(async () => {
      try {
        const [tax, projects] = await Promise.all([api.taxonomy(), api.projects()])
        const list = await api.pages(projects.current)
        if (!cancelled) loaded(tax, projects.current, list)
      } catch (exc) {
        if (!cancelled) failed(exc instanceof Error ? exc.message : String(exc))
      }
    })()
    return () => {
      cancelled = true
    }
  }, [startLoading, loaded, failed])

  return (
    <div className="app">
      <header className="app__header">
        <h1>annotool</h1>
        {project && <span className="app__project">{project}</span>}
        {taxonomy && (
          <span className="app__taxonomy">
            {taxonomy.name} v{taxonomy.version}
          </span>
        )}
      </header>

      <main className="app__main">
        {status === 'loading' && <p role="status">Loading…</p>}
        {status === 'error' && (
          <p role="alert" className="app__error">
            Couldn't reach the annotool server: {error}. Start it with{' '}
            <code>uv run annotool serve --project &lt;name&gt;</code>.
          </p>
        )}
        {status === 'ready' && (
          <>
            <nav className="app__sidebar">
              <PageList pages={pages} currentPageId={currentPageId} onOpen={openPage} />
            </nav>
            <section className="app__canvas">
              {saveState === 'conflict' && (
                <div role="alert" className="app__banner">
                  <span title={saveError ?? undefined}>
                    Not saved: this page's annotations.json was changed elsewhere (another tab or
                    a script). Nothing was overwritten.
                  </span>
                  <button type="button" onClick={() => void reloadPage()}>
                    Reload page
                  </button>
                </div>
              )}
              {pageStatus === 'error' && (
                <p role="alert" className="app__error">
                  Couldn't open this page: {pageError}
                </p>
              )}
              {page && project && currentPageId && pageStatus !== 'error' && (
                <Stage
                  project={project}
                  pageId={currentPageId}
                  page={page}
                  attributeIds={attributeIds}
                />
              )}
            </section>
          </>
        )}
      </main>
    </div>
  )
}

function PageList(props: {
  pages: PageSummary[]
  currentPageId: string | null
  onOpen: (id: string) => void
}) {
  if (props.pages.length === 0) {
    return <p>This project has no pages yet. Capture some with <code>annotool capture</code>.</p>
  }
  return (
    <ul className="pages" aria-label="Pages">
      {props.pages.map((page) => {
        const { boxes, complete } = page.progress
        return (
          <li key={page.id}>
            <button
              type="button"
              className="pages__item"
              aria-current={page.id === props.currentPageId ? 'true' : undefined}
              onClick={() => props.onOpen(page.id)}
            >
              <span className="pages__id">{page.id}</span>
              <span className="pages__progress">
                {page.blocked ? 'blocked' : `${complete}/${boxes} boxes complete`}
              </span>
            </button>
          </li>
        )
      })}
    </ul>
  )
}
