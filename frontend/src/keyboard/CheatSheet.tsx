import type { Keymap } from './keymap'

const GENERAL: [string, string][] = [
  ['D / S', 'Draw / select tool'],
  ['Shift+D', 'Draw template sections (boxes inside inherit them)'],
  ['Shift+click, drag', 'Add to selection, rubber band'],
  ['Drag a box (select tool)', 'Move it, or the whole selection'],
  ['Drag an edge or corner', 'Resize the selected box (any tool)'],
  ['p, then 1–9', 'Paint with a preset: click or drag over boxes; Esc stops'],
  ['Tab / Shift+Tab', 'Next / previous box that needs labels'],
  ['Delete / X', 'Delete selected boxes'],
  ['Esc', 'Cancel, then deselect'],
  ['Ctrl+Z / Ctrl+Shift+Z', 'Undo / redo'],
  ['Ctrl+S', 'Save now (autosave runs anyway)'],
  ['] / [', 'Next / previous page'],
  ['+ / - / Ctrl+0', 'Zoom in / out / fit width'],
  ['Ctrl+wheel', 'Zoom around the cursor'],
  ['Middle-drag, Space+drag', 'Pan'],
  ['/', 'Search any label or preset'],
  ['?', 'Show / hide this sheet'],
]

/** Every shortcut, with the label shortcuts generated from the taxonomy. */
export function CheatSheet({ keymap, onClose }: { keymap: Keymap; onClose: () => void }) {
  return (
    <div className="cheatsheet__backdrop" onClick={onClose}>
      <div
        className="cheatsheet"
        role="dialog"
        aria-modal="true"
        aria-label="Keyboard shortcuts"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="cheatsheet__header">
          <h2>Keyboard shortcuts</h2>
          <button type="button" onClick={onClose} aria-label="Close">
            ×
          </button>
        </header>
        <p className="cheatsheet__hint">
          Select boxes, press an attribute key, then the option's letter, or a digit for a whole
          preset. Labels apply to every selected box.
        </p>
        <div className="cheatsheet__columns">
          {keymap.attributes.map((attribute) => (
            <section key={attribute.id} aria-label={attribute.label}>
              <h3>
                <kbd>{attribute.hotkey}</kbd> {attribute.label}
              </h3>
              <dl>
                {attribute.options.map((option) => (
                  <div key={option.value}>
                    <dt>
                      <kbd>{option.key}</kbd>
                    </dt>
                    <dd>{option.value}</dd>
                  </div>
                ))}
              </dl>
            </section>
          ))}
          {keymap.presets.length > 0 && (
            <section aria-label="Presets">
              <h3>Presets</h3>
              <dl>
                {keymap.presets.map((preset) => (
                  <div key={preset.key}>
                    <dt>
                      <kbd>{preset.key}</kbd>
                    </dt>
                    <dd>{Object.values(preset.labels).join(' · ')}</dd>
                  </div>
                ))}
              </dl>
            </section>
          )}
          <section aria-label="General">
            <h3>General</h3>
            <dl>
              {GENERAL.map(([keys, what]) => (
                <div key={keys}>
                  <dt>
                    <kbd>{keys}</kbd>
                  </dt>
                  <dd>{what}</dd>
                </div>
              ))}
            </dl>
          </section>
        </div>
      </div>
    </div>
  )
}
