// The Suggest button (4.1): run the server's suggesters on the open page and take the
// merged result as one undo step. The server never overwrites a person's labels.

import { ApiError, api } from '../api/client'
import type { SuggestReport } from '../api/types'
import { useAppStore } from '../state/store'
import { saveNow } from './autosave'

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`

/** "Suggestions: +3 boxes, 12 labels, kept 2 of your labels (dom, rule)". */
export function summarizeReports(reports: SuggestReport[]): string {
  const ok = reports.filter((r) => !r.error)
  const failures = reports.filter((r) => r.error).map((r) => `${r.suggester} failed: ${r.error}`)
  let head = ''
  if (ok.length > 0) {
    const sum = (key: 'boxes_added' | 'labels_set' | 'kept_human') =>
      ok.reduce((total, r) => total + r[key], 0)
    const parts = ok.some((r) => r.changed)
      ? [`+${plural(sum('boxes_added'), 'box', 'boxes')}`, plural(sum('labels_set'), 'label', 'labels')]
      : ['nothing new']
    if (sum('kept_human') > 0) parts.push(`kept ${sum('kept_human')} of your labels`)
    head = `${parts.join(', ')} (${ok.map((r) => r.suggester).join(', ')})`
  }
  return `Suggestions: ${[head, ...failures].filter(Boolean).join('. ')}`
}

/** Wait for an autosave already on its way, so its new ETag is the one we send. */
function settled(): Promise<void> {
  if (useAppStore.getState().saveState !== 'saving') return Promise.resolve()
  return new Promise((resolve) => {
    const stop = useAppStore.subscribe((s) => {
      if (s.saveState !== 'saving') {
        stop()
        resolve()
      }
    })
  })
}

/**
 * Save any pending edits, run the suggesters on the saved page, and apply the result.
 * If the page is edited while the suggesters run, the result is not applied over those
 * edits: the page is flagged as changed elsewhere, like any other conflict.
 */
export async function runSuggest(): Promise<void> {
  const start = useAppStore.getState()
  if (!start.page || !start.project || !start.pageId) return
  if (start.suggesting || start.suggesters.length === 0 || start.saveState === 'conflict') return
  const { project, pageId } = start
  start.setSuggesting(true)
  try {
    await settled()
    await saveNow()
    const before = useAppStore.getState()
    if (before.pageId !== pageId || !before.page) return
    if (before.docVersion !== before.savedVersion) {
      before.setNotice('Suggest needs the page saved first, and saving failed. Try again.')
      return
    }
    const version = before.docVersion
    const result = await api.suggest(project, pageId, before.page.etag)
    const after = useAppStore.getState()
    if (after.pageId !== pageId) return // moved to another page meanwhile
    if (after.docVersion !== version) {
      after.saveConflict('The page was edited while the suggesters ran; reload it to see both.')
      return
    }
    after.applySuggestions(pageId, result)
    useAppStore.getState().setNotice(summarizeReports(result.reports))
  } catch (exc) {
    const message = exc instanceof Error ? exc.message : String(exc)
    const s = useAppStore.getState()
    if (exc instanceof ApiError && exc.status === 412) s.saveConflict(message)
    else s.setNotice(`Suggest failed: ${message}`)
  } finally {
    useAppStore.getState().setSuggesting(false)
  }
}
