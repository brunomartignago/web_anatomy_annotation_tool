import { useEffect } from 'react'

import { useAppStore } from '../state/store'
import type { Keymap } from './keymap'
import { PAINT_PICKER, pressKey } from './keymap'

const isTyping = (target: EventTarget | null) =>
  target instanceof HTMLElement &&
  (target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName))

/**
 * Label shortcuts (attribute hotkey, then option letter), presets and painting, and the
 * `?` cheat sheet.
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
      if (event.key === '/' && !s.cheatSheet && !s.palette) {
        consume() // or the "/" would be typed into the palette's search box
        s.setPalette(true)
        return
      }
      if (s.cheatSheet) {
        if (event.key === 'Escape') {
          consume()
          s.setCheatSheet(false)
        }
        return
      }

      // Painting (3.5): Esc or p stops it, before anything else uses those keys.
      if (s.paint && s.picker === null && (event.key === 'Escape' || event.key.toLowerCase() === 'p')) {
        consume()
        s.setPaint(null)
        return
      }

      const action = pressKey(keymap, s.picker, event.key)
      switch (action.type) {
        case 'pass':
          return
        case 'open':
          // Painting needs no selection; labeling does.
          if (action.attribute !== PAINT_PICKER && s.selectedIds.length === 0) return
          s.setPicker(action.attribute)
          break
        case 'set':
          s.setLabel(action.attribute, action.value)
          s.setPicker(null)
          break
        case 'preset':
          if (s.paint) {
            s.setPaint(action.preset) // while painting, a digit switches the preset
            break
          }
          if (s.selectedIds.length === 0) return
          s.applyPreset(action.preset.labels)
          break
        case 'paint':
          s.setPaint(action.preset)
          s.setPicker(null)
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
