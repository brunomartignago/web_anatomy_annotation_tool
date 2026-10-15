import { describe, expect, it } from 'vitest'

import type { Annotation, PageAnnotationFileV1 } from './annotation'

// Mostly a compile-time check (`tsc -b` runs in `pnpm build`): the generated types must
// accept a real annotation file, with bbox as a 4-number tuple, not unknown[].
describe('generated annotation types', () => {
  it('describe a schema v1 file', () => {
    const box: Annotation = {
      id: '01JA0000000000000000000000',
      kind: 'element',
      bbox: [473, 2.5, 970.9, 250.8],
      labels: { Form: 'Typo', Function: 'Link' },
      source: 'legacy',
      status: 'accepted',
    }
    const file: PageAnnotationFileV1 = {
      schema_version: '1.0',
      taxonomy: { id: 'web-ui', version: '1.0' },
      page: { id: 'edition_cnn_com', image: 'page.png', width: 1920, height: 7681 },
      annotations: [box],
    }
    const [, , width, height] = file.annotations[0].bbox
    expect(width * height).toBeGreaterThan(0)
  })
})
