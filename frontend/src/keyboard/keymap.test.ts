import { describe, expect, it } from 'vitest'

import type { Taxonomy } from '../api/types'
import { loadWebUi } from '../test/webUi'
import { PAINT_PICKER, RESERVED_KEYS, buildKeymap, pressKey } from './keymap'

// The real taxonomy: shortcuts must come from it, and the ✅ is checked against it.
const WEB_UI = loadWebUi()

function type(keymap: ReturnType<typeof buildKeymap>, keys: string[]) {
  let picker: string | null = null
  const actions = []
  for (const key of keys) {
    const action = pressKey(keymap, picker, key)
    actions.push(action)
    if (action.type === 'open') picker = action.attribute
    else if (action.type === 'set' || action.type === 'close') picker = null
  }
  return { actions, picker }
}

describe('keymap from web-ui.yaml', () => {
  const keymap = buildKeymap(WEB_UI)

  it('every active option takes at most 2 keystrokes (✅ 3.1)', () => {
    let checked = 0
    for (const attribute of WEB_UI.attributes) {
      for (const option of attribute.options.filter((o) => o.status !== 'proposed')) {
        const { actions } = type(keymap, [attribute.hotkey, option.key])
        expect(actions.at(-1), `${attribute.id} → ${option.value}`).toEqual({
          type: 'set',
          attribute: attribute.id,
          value: option.value,
        })
        checked += 1
      }
    }
    expect(checked).toBeGreaterThan(35) // all four attributes, not a vacuous pass
  })

  it('reaches the options v2 could not: Heading and Right Menu', () => {
    expect(type(keymap, ['n', 'h']).actions.at(-1)).toEqual({
      type: 'set',
      attribute: 'Function',
      value: 'Heading',
    })
    expect(type(keymap, ['t', 'n']).actions.at(-1)).toEqual({
      type: 'set',
      attribute: 'Taxonomy',
      value: 'Right Menu',
    })
  })

  it("has no clashes with the app's own keys", () => {
    expect(keymap.conflicts).toEqual([])
  })

  it('proposed options are not reachable', () => {
    // Column 5 (key "5") is proposed in the YAML.
    expect(type(keymap, ['t', '5']).actions.at(-1)).toEqual({ type: 'none' })
  })
})

describe('picker state machine', () => {
  const keymap = buildKeymap(WEB_UI)

  it('a hotkey opens its picker; unrelated keys pass through when closed', () => {
    expect(pressKey(keymap, null, 'f')).toEqual({ type: 'open', attribute: 'Form' })
    expect(pressKey(keymap, null, 'q')).toEqual({ type: 'pass' })
    expect(pressKey(keymap, null, 'd')).toEqual({ type: 'pass' }) // the app's draw key
  })

  it('inside a picker, option letters win over app keys and other hotkeys', () => {
    // "d" is Dropdown in the Function picker, not the draw tool.
    expect(pressKey(keymap, 'Function', 'd')).toEqual({
      type: 'set',
      attribute: 'Function',
      value: 'Dropdown',
    })
    // "c" is Icon in the Form picker, even though "c" is also Component's hotkey.
    expect(pressKey(keymap, 'Form', 'c')).toEqual({ type: 'set', attribute: 'Form', value: 'Icon' })
  })

  it('Escape or the same hotkey closes; another hotkey switches', () => {
    expect(pressKey(keymap, 'Form', 'Escape')).toEqual({ type: 'close' })
    expect(pressKey(keymap, 'Form', 'f')).toEqual({ type: 'close' })
    expect(pressKey(keymap, 'Form', 'n')).toEqual({ type: 'open', attribute: 'Function' })
  })

  it('an unknown letter in an open picker is swallowed, not passed to the app', () => {
    expect(pressKey(keymap, 'Form', 'q')).toEqual({ type: 'none' })
  })

  it('Tab, Delete and other named keys still reach the app with a picker open', () => {
    for (const key of ['Tab', 'Delete', 'Enter', 'ArrowDown']) {
      expect(pressKey(keymap, 'Form', key)).toEqual({ type: 'pass' })
    }
  })

  it('keys are case-insensitive', () => {
    expect(pressKey(keymap, null, 'F')).toEqual({ type: 'open', attribute: 'Form' })
  })
})

describe('presets (3.2)', () => {
  const keymap = buildKeymap(WEB_UI)

  it('come from the YAML in order, keyed 1-9', () => {
    expect(keymap.presets.map((p) => p.key)).toEqual(['1', '2', '3', '4', '5', '6', '7', '8', '9'])
    expect(keymap.presets[0].labels).toEqual({ Form: 'Typo', Function: 'Text', Component: 'Blank' })
  })

  it('a digit applies its preset when no picker is open', () => {
    expect(pressKey(keymap, null, '3')).toEqual({
      type: 'preset',
      preset: { key: '3', labels: { Form: 'Typo', Function: 'Heading', Component: 'Blank' } },
    })
  })

  it('inside a picker, digits are still option letters (t 1 = Column 1)', () => {
    expect(pressKey(keymap, 'Taxonomy', '1')).toEqual({
      type: 'set',
      attribute: 'Taxonomy',
      value: 'Column 1',
    })
  })

  it('a digit without a preset passes through', () => {
    expect(pressKey(keymap, null, '0')).toEqual({ type: 'pass' })
  })

  it('drops presets that use a value missing from the taxonomy', () => {
    const custom: Taxonomy = {
      ...WEB_UI,
      presets: [{ key: '1', labels: { Form: 'Hologram' } }, ...WEB_UI.presets.slice(1)],
    }
    const { presets, conflicts } = buildKeymap(custom)
    expect(presets.map((p) => p.key)).not.toContain('1')
    expect(conflicts.some((c) => c.includes('Hologram'))).toBe(true)
  })
})

describe('paint picker (3.5)', () => {
  const keymap = buildKeymap(WEB_UI)

  it('p opens the paint picker, then a digit picks the preset to paint with', () => {
    expect(pressKey(keymap, null, 'p')).toEqual({ type: 'open', attribute: PAINT_PICKER })
    expect(pressKey(keymap, PAINT_PICKER, '2')).toEqual({
      type: 'paint',
      preset: { key: '2', labels: keymap.presets[1].labels },
    })
  })

  it('Escape or p again closes it; other keys are used up', () => {
    expect(pressKey(keymap, PAINT_PICKER, 'Escape')).toEqual({ type: 'close' })
    expect(pressKey(keymap, PAINT_PICKER, 'P')).toEqual({ type: 'close' })
    expect(pressKey(keymap, PAINT_PICKER, 'f')).toEqual({ type: 'none' })
    expect(pressKey(keymap, PAINT_PICKER, '0')).toEqual({ type: 'none' }) // no preset 0
    expect(pressKey(keymap, PAINT_PICKER, 'Tab')).toEqual({ type: 'pass' })
  })

  it('p is reserved, so no attribute can take it', () => {
    expect(RESERVED_KEYS.has('p')).toBe(true)
  })

  it('a is reserved for Shift+A, select similar (3.6a)', () => {
    expect(RESERVED_KEYS.has('a')).toBe(true)
  })
})

describe('conflicts in a custom taxonomy', () => {
  it('reports hotkeys that collide with app keys or the preset digits', () => {
    const custom: Taxonomy = {
      ...WEB_UI,
      presets: [],
      attributes: [
        { ...WEB_UI.attributes[0], hotkey: 'd' },
        { ...WEB_UI.attributes[1], hotkey: '3' },
      ],
    }
    const { conflicts, attributes } = buildKeymap(custom)
    expect(conflicts).toHaveLength(2)
    expect(conflicts[0]).toContain('"d"')
    expect(conflicts[1]).toContain('"3"')
    expect(attributes).toHaveLength(0) // conflicting hotkeys are disabled, not half-working
  })

  it('lists the reserved keys', () => {
    for (const key of ['d', 's', 'x', '?', '[', ']']) expect(RESERVED_KEYS.has(key)).toBe(true)
  })
})
