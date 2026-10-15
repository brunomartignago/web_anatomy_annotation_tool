import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { parse } from 'yaml'

import type { Taxonomy } from '../api/types'

/**
 * The repo's real taxonomies/web-ui.yaml, with the same defaults the server's loader
 * (backend/src/annotool/taxonomy.py) fills in: `label` = `id`, option `status` = active.
 * Vitest runs from frontend/, so the file is one level up.
 */
export function loadWebUi(): Taxonomy {
  const raw = parse(readFileSync(resolve(process.cwd(), '../taxonomies/web-ui.yaml'), 'utf-8'))
  return {
    ...raw,
    presets: raw.presets ?? [],
    rules: raw.rules ?? {},
    attributes: raw.attributes.map((a: Taxonomy['attributes'][number]) => ({
      ...a,
      inherit_from_parent: a.inherit_from_parent ?? false,
      computed_by_rules: a.computed_by_rules ?? false,
      label: a.label ?? a.id,
      options: a.options.map((o) => ({ ...o, status: o.status ?? 'active' })),
    })),
  }
}
