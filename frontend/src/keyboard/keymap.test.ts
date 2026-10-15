import { describe, expect, it } from 'vitest'

import type { Taxonomy } from '../api/types'
import { loadWebUi } from '../test/webUi'
import { RESERVED_KEYS, buildKeymap, pressKey } from './keymap'

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

describe('conflicts in a custom taxonomy', () => {
  it('reports hotkeys that collide with app keys or the preset digits', () => {
    const custom: Taxonomy = {
      ...WEB_UI,
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
