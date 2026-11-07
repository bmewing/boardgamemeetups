/**
 * Reads each piece's drawing from its SVG file in ./svg (see the README there).
 *
 * A file gives three groups, found by id (or an Inkscape layer's label): `body`, filled with
 * the person's color and outlined as one silhouette; `details`, filled in the outline's ink;
 * and `lines`, stroked in that ink. Colors and strokes in the file are ignored: the app
 * brings its own, so every piece looks like it belongs to the same set.
 */

import type { PieceName } from './shapes'

const SVG_NS = 'http://www.w3.org/2000/svg'
const ROLES = ['body', 'details', 'lines'] as const
type Role = (typeof ROLES)[number]

/** One element to draw, already reduced to the four kinds the app renders. */
export interface Shape {
  tag: 'path' | 'circle' | 'ellipse' | 'rect'
  attrs: Record<string, string>
}

export type PieceDrawingData = Record<Role, Shape[]>

/** The attributes kept for each kind; everything else (fills, ids, classes) is dropped. */
const GEOMETRY: Record<Shape['tag'], string[]> = {
  path: ['d'],
  circle: ['cx', 'cy', 'r'],
  ellipse: ['cx', 'cy', 'rx', 'ry'],
  rect: ['x', 'y', 'width', 'height', 'rx', 'ry'],
}

/** Elements that never draw anything, so they can sit anywhere. */
const IGNORED = new Set(['title', 'desc', 'metadata', 'defs', 'style', 'namedview'])

function roleOf(el: Element): Role | undefined {
  const names = [
    el.getAttribute('id'),
    el.getAttribute('inkscape:label'),
    el.getAttribute('data-name'),
  ]
  return ROLES.find((role) => names.some((n) => n?.trim().toLowerCase() === role))
}

/** `x1,y1 x2,y2 …` as path commands. */
function pointsToPath(points: string, close: boolean): string {
  const numbers = points.trim().split(/[\s,]+/)
  const pairs: string[] = []
  for (let i = 0; i + 1 < numbers.length; i += 2) pairs.push(`${numbers[i]} ${numbers[i + 1]}`)
  return `M${pairs.join('L')}${close ? 'Z' : ''}`
}

function fillRuleOf(el: Element): string | undefined {
  const fromStyle = /fill-rule\s*:\s*(evenodd|nonzero)/.exec(el.getAttribute('style') ?? '')
  return el.getAttribute('fill-rule') ?? fromStyle?.[1]
}

function toShape(el: Element, where: string): Shape {
  const tag = el.localName
  let shape: Shape
  if (tag === 'line') {
    const [x1, y1, x2, y2] = ['x1', 'y1', 'x2', 'y2'].map((a) => el.getAttribute(a) ?? '0')
    shape = { tag: 'path', attrs: { d: `M${x1} ${y1}L${x2} ${y2}` } }
  } else if (tag === 'polyline' || tag === 'polygon') {
    shape = {
      tag: 'path',
      attrs: { d: pointsToPath(el.getAttribute('points') ?? '', tag === 'polygon') },
    }
  } else if (tag in GEOMETRY) {
    const kind = tag as Shape['tag']
    const attrs: Record<string, string> = {}
    for (const name of GEOMETRY[kind]) {
      const value = el.getAttribute(name)
      if (value !== null) attrs[name] = value
    }
    shape = { tag: kind, attrs }
  } else if (tag === 'text') {
    throw new Error(`${where}: has text. Convert it to a path ("Object to path" / "Outline").`)
  } else {
    throw new Error(
      `${where}: has a <${tag}>, which pieces can't use. Stick to paths, circles, ellipses, ` +
        'rectangles, lines and polygons.',
    )
  }
  const fillRule = fillRuleOf(el)
  if (fillRule) shape.attrs.fillRule = fillRule // React's name for fill-rule
  return shape
}

/**
 * Turns one piece's SVG source into what the app draws. Throws, saying what to fix, if the
 * file breaks the rules in the README.
 */
export function parsePieceSvg(source: string, fileName = 'This file'): PieceDrawingData {
  const doc = new DOMParser().parseFromString(source, 'image/svg+xml')
  const svg = doc.documentElement
  if (doc.getElementsByTagName('parsererror').length || svg.localName !== 'svg') {
    throw new Error(`${fileName}: isn't a readable SVG.`)
  }
  const viewBox = (svg.getAttribute('viewBox') ?? '')
    .trim()
    .split(/[\s,]+/)
    .map(Number)
  if (viewBox.join(' ') !== '0 0 100 100') {
    throw new Error(`${fileName}: the canvas must be viewBox="0 0 100 100".`)
  }

  const drawing: PieceDrawingData = { body: [], details: [], lines: [] }
  const walk = (el: Element, role: Role | undefined) => {
    for (const child of Array.from(el.children)) {
      const tag = child.localName
      if (IGNORED.has(tag) || child.namespaceURI !== SVG_NS) continue
      if (child.hasAttribute('transform')) {
        throw new Error(
          `${fileName}: <${tag}${child.id ? ` id="${child.id}"` : ''}> is moved, scaled or ` +
            'rotated with a transform. Flatten it (in Inkscape: Path → Object to path, or Edit → ' +
            'Preferences → Behavior → Transforms → Store transformation: Optimized).',
        )
      }
      if (tag === 'g' || tag === 'svg') {
        walk(child, roleOf(child) ?? role)
        continue
      }
      if (!role) {
        throw new Error(
          `${fileName}: a <${tag}> sits outside the body, details and lines groups, so the app ` +
            "wouldn't know how to color it.",
        )
      }
      drawing[role].push(toShape(child, fileName))
    }
  }
  walk(svg, undefined)

  if (!drawing.body.length) throw new Error(`${fileName}: the body group is empty or missing.`)
  return drawing
}

/** The raw SVG files, by piece name. */
export const PIECE_FILES: Record<string, string> = Object.fromEntries(
  Object.entries(
    import.meta.glob<string>('./svg/*.svg', { query: '?raw', import: 'default', eager: true }),
  ).map(([path, source]) => [path.slice('./svg/'.length, -'.svg'.length), source]),
)

/** What a piece is drawn as if its file is missing or broken, so one bad file can't break a page. */
const FALLBACK: PieceDrawingData = {
  body: [
    {
      tag: 'path',
      attrs: {
        d: 'M50 6c-10.5 0-16.5 8-16.5 17 0 5 1.6 8.6 3.4 11C24 38.4 9 44 6.5 53.5 5 59.8 11.5 63 21 63.5 17 73 11.5 84 9 94h29c3-7.5 7-13.5 12-13.5S59 86.5 62 94h29c-2.5-10-8-21-12-30.5 9.5-.5 16-3.7 14.5-10C91 44 76 38.4 63.1 34c1.8-2.4 3.4-6 3.4-11C66.5 14 60.5 6 50 6z',
      },
    },
  ],
  details: [],
  lines: [],
}

const cache = new Map<PieceName, PieceDrawingData>()

export function pieceDrawing(piece: PieceName): PieceDrawingData {
  let drawing = cache.get(piece)
  if (!drawing) {
    try {
      const source = PIECE_FILES[piece]
      if (source === undefined) throw new Error(`There's no svg/${piece}.svg.`)
      drawing = parsePieceSvg(source, `svg/${piece}.svg`)
    } catch (error) {
      console.error(error)
      drawing = FALLBACK
    }
    cache.set(piece, drawing)
  }
  return drawing
}
