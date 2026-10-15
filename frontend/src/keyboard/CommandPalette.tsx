import { useMemo, useState } from 'react'
import type { KeyboardEvent } from 'react'

import { useAppStore } from '../state/store'
import type { Command } from './palette'
import { searchCommands } from './palette'

const MAX_RESULTS = 12

/** `/`: type to find any value or preset, Enter applies it to the selected boxes. */
export function CommandPalette({
  commands,
  onClose,
}: {
  commands: Command[]
  onClose: () => void
}) {
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)
  const selectedCount = useAppStore((s) => s.selectedIds.length)
  const results = useMemo(
    () => searchCommands(commands, query).slice(0, MAX_RESULTS),
    [commands, query],
  )

  const run = (command: Command | undefined) => {
    if (!command || selectedCount === 0) return
    const s = useAppStore.getState()
    if (command.kind === 'label') s.setLabel(command.attribute, command.value)
    else s.applyPreset(command.labels)
    onClose()
  }

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setActive((i) => Math.min(i + 1, results.length - 1))
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setActive((i) => Math.max(i - 1, 0))
    } else if (event.key === 'Enter') {
      event.preventDefault()
      run(results[active])
    } else if (event.key === 'Escape') {
      event.preventDefault()
      onClose()
    }
  }

  return (
    <div className="palette__backdrop" onClick={onClose}>
      <div
        className="palette"
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
        onClick={(event) => event.stopPropagation()}
      >
        <input
          className="palette__input"
          aria-label="Search labels and presets"
          placeholder="Type a label or preset… (e.g. hea → Heading)"
          role="combobox"
          aria-expanded="true"
          aria-controls="palette-results"
          aria-activedescendant={results[active] ? `palette-${results[active].id}` : undefined}
          autoFocus
          value={query}
          onChange={(event) => {
            setQuery(event.target.value)
            setActive(0)
          }}
          onKeyDown={onKeyDown}
        />
        {selectedCount === 0 && (
          <p className="palette__hint">Select boxes first: results can't be applied yet.</p>
        )}
        {results.length === 0 ? (
          <p className="palette__hint">No label or preset matches “{query}”.</p>
        ) : (
          <ul id="palette-results" className="palette__results" role="listbox">
            {results.map((command, i) => (
              <li
                key={command.id}
                id={`palette-${command.id}`}
                role="option"
                aria-selected={i === active}
                className="palette__item"
                onMouseEnter={() => setActive(i)}
                onClick={() => run(command)}
              >
                <span className="palette__title">{command.title}</span>
                <span className="palette__detail">{command.detail}</span>
                <kbd className="palette__shortcut">{command.shortcut}</kbd>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
