import { describe, expect, it } from 'vitest'

import { parsePieceSvg, PIECE_FILES } from './drawings'
import { PIECE_GROUPS, PIECE_LABELS } from './shapes'

const NAMES = Object.keys(PIECE_LABELS)

const svg = (inner: string, viewBox = '0 0 100 100') =>
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${viewBox}">${inner}</svg>`

describe('the piece files', () => {
  it.each(NAMES)('svg/%s.svg follows the rules', (name) => {
    const source = PIECE_FILES[name]
    expect(source, `svg/${name}.svg is missing`).toBeDefined()
    expect(() => parsePieceSvg(source, `svg/${name}.svg`)).not.toThrow()
  })

  it('has no files for pieces the app doesn’t know', () => {
    const unknown = Object.keys(PIECE_FILES).filter((name) => !NAMES.includes(name))
    expect(unknown, 'add these to app/pieces.py and PIECE_LABELS, or rename them').toEqual([])
  })

  it('offers every piece in exactly one picker group', () => {
    const grouped = PIECE_GROUPS.flatMap((group) => group.pieces)
    expect([...grouped].sort()).toEqual([...NAMES].sort())
  })
})

describe('parsePieceSvg', () => {
  it('sorts shapes into body, details and lines, keeping only their geometry', () => {
    const drawing = parsePieceSvg(
      svg(`
        <g id="body" fill="red"><rect x="10" y="10" width="80" height="80" rx="8" style="fill:blue"/></g>
        <g id="details"><circle cx="50" cy="50" r="5" fill="green"/></g>
        <g id="lines"><line x1="10" y1="20" x2="30" y2="40" stroke="black"/></g>`),
    )
    expect(drawing).toEqual({
      body: [{ tag: 'rect', attrs: { x: '10', y: '10', width: '80', height: '80', rx: '8' } }],
      details: [{ tag: 'circle', attrs: { cx: '50', cy: '50', r: '5' } }],
      lines: [{ tag: 'path', attrs: { d: 'M10 20L30 40' } }],
    })
  })

  it('reads Inkscape layers, nested groups, polygons and even-odd holes', () => {
    const drawing = parsePieceSvg(`
      <svg xmlns="http://www.w3.org/2000/svg" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"
           xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd" viewBox="0 0 100 100">
        <sodipodi:namedview id="namedview1"/>
        <defs id="defs1"/>
        <g inkscape:groupmode="layer" id="layer1" inkscape:label="Body">
          <g><polygon points="10,90 50,10 90,90"/></g>
          <path d="M0 0H100V100H0Z M40 40H60V60H40Z" style="fill:#fff;fill-rule:evenodd"/>
        </g>
      </svg>`)
    expect(drawing.body).toEqual([
      { tag: 'path', attrs: { d: 'M10 90L50 10L90 90Z' } },
      { tag: 'path', attrs: { d: 'M0 0H100V100H0Z M40 40H60V60H40Z', fillRule: 'evenodd' } },
    ])
  })

  it.each([
    ['the wrong canvas', svg('<g id="body"><circle r="5"/></g>', '0 0 24 24'), 'viewBox'],
    [
      'a transform',
      svg('<g id="body"><rect width="5" height="5" transform="rotate(45)"/></g>'),
      'transform',
    ],
    ['text', svg('<g id="body"><text>Hi</text></g>'), 'text'],
    ['an image', svg('<g id="body"><image href="x.png"/></g>'), '<image>'],
    [
      'a shape outside the groups',
      svg('<g id="body"><circle r="5"/></g><circle r="5"/>'),
      'outside',
    ],
    ['no body', svg('<g id="details"><circle r="5"/></g>'), 'body group'],
    ['broken XML', '<svg', 'readable'],
  ])('rejects %s', (_, source, message) => {
    expect(() => parsePieceSvg(source)).toThrow(message)
  })
})
