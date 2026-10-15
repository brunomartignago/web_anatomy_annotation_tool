import { useEffect } from 'react'

import { useAppStore } from '../state/store'
import type { Keymap } from './keymap'
import { pressKey } from './keymap'

const isTyping = (target: EventTarget | null) =>
  target instanceof HTMLElement &&
  (target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName))

/**
 * Label shortcuts (attribute hotkey, then option letter) and the `?` cheat sheet.
 * Listens in the capture phase so that, inside a picker, a letter like "d" sets Dropdown
 * instead of reaching the canvas as "draw tool". Keys it doesn't use pass through.
 */
export function useLabelKeys(keymap: Keymap | null): void {
  useEffect(() => {
    if (!keymap) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (isTyping(event.target) || event.ctrlKey || event.metaKey || event.altKey) return
      const s = useAppStore.getState()
      const consume = () => {
        event.preventDefault()
        event.stopPropagation()
      }

      if (event.key === '?') {
        consume()
        s.setCheatSheet(!s.cheatSheet)
        return
      }
      if (s.cheatSheet) {
        if (event.key === 'Escape') {
          consume()
          s.setCheatSheet(false)
        }
        return
      }

      const action = pressKey(keymap, s.picker, event.key)
      switch (action.type) {
        case 'pass':
          return
        case 'open':
          if (s.selectedIds.length === 0) return // nothing to label
          s.setPicker(action.attribute)
          break
        case 'set':
          s.setLabel(action.attribute, action.value)
          s.setPicker(null)
          break
        case 'preset':
          if (s.selectedIds.length === 0) return
          s.applyPreset(action.labels)
          break
        case 'close':
          s.setPicker(null)
          break
        case 'none':
          break
      }
      consume()
    }
    window.addEventListener('keydown', onKeyDown, { capture: true })
    return () => window.removeEventListener('keydown', onKeyDown, { capture: true })
  }, [keymap])
}
