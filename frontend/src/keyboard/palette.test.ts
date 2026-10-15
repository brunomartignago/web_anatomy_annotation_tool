import { describe, expect, it } from 'vitest'

import { loadWebUi } from '../test/webUi'
import { buildKeymap } from './keymap'
import { buildCommands, fuzzyScore, searchCommands } from './palette'

const KEYMAP = buildKeymap(loadWebUi())
const COMMANDS = buildCommands(KEYMAP)
const titles = (query: string) => searchCommands(COMMANDS, query).map((c) => c.title)

describe('fuzzyScore', () => {
  it('matches letters in order, case-insensitively', () => {
    expect(fuzzyScore('hea', 'Heading')).not.toBeNull()
    expect(fuzzyScore('HDG', 'Heading')).not.toBeNull()
    expect(fuzzyScore('gh', 'Heading')).toBeNull() // out of order
    expect(fuzzyScore('xyz', 'Heading')).toBeNull()
  })

  it('prefers prefixes, then word starts, then scattered letters', () => {
    const prefix = fuzzyScore('men', 'Menu')!
    const wordStart = fuzzyScore('men', 'Left Menu')!
    const scattered = fuzzyScore('men', 'Text input')
    expect(prefix).toBeGreaterThan(wordStart)
    expect(scattered).toBeNull() // no "m" in Text input
    expect(fuzzyScore('lm', 'Left Menu')!).toBeGreaterThan(fuzzyScore('lm', 'Illustration')! ?? -1)
  })
})

describe('commands from web-ui.yaml', () => {
  it('include every active value and every preset, but no proposed values', () => {
    const values = COMMANDS.filter((c) => c.kind === 'label')
    const presets = COMMANDS.filter((c) => c.kind === 'preset')
    expect(values).toHaveLength(4 + 13 + 10 + 12) // Column 5 and Overlay are proposed
    expect(presets).toHaveLength(9)
    expect(COMMANDS.some((c) => c.title === 'Column 5' || c.title === 'Overlay')).toBe(false)
  })

  it('describe where each value lives and its shortcut', () => {
    const heading = COMMANDS.find((c) => c.title === 'Heading')!
    expect(heading).toMatchObject({ kind: 'label', attribute: 'Function', value: 'Heading' })
    expect(heading.detail).toBe('Function')
    expect(heading.shortcut).toBe('n h')
    const preset = COMMANDS.find((c) => c.kind === 'preset')!
    expect(preset).toMatchObject({ title: 'Typo · Text · Blank', detail: 'Preset 1', shortcut: '1' })
  })
})

describe('searchCommands', () => {
  it('"hea" finds Heading first (✅ 3.3)', () => {
    expect(titles('hea')[0]).toBe('Heading')
    expect(titles('hea')).toContain('Header') // the template section is listed too
  })

  it('finds values by abbreviation and by attribute name', () => {
    expect(titles('rmen')[0]).toBe('Right Menu')
    expect(titles('section foot')[0]).toBe('Footer') // "Template section"
    expect(titles('function link')[0]).toBe('Link')
  })

  it('finds presets by their values', () => {
    const results = searchCommands(COMMANDS, 'typo card')
    expect(results[0]).toMatchObject({ kind: 'preset', title: 'Typo · Text · Card' })
  })

  it('an empty query lists everything in taxonomy order; nonsense lists nothing', () => {
    expect(searchCommands(COMMANDS, '')).toHaveLength(COMMANDS.length)
    expect(titles('')[0]).toBe('Typo')
    expect(titles('qqq')).toEqual([])
  })
})
