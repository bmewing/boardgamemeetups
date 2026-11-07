/**
 * The game pieces people pick to stand for them, drawn in a 100 × 100 box. The names match
 * the backend's (app/pieces.py).
 *
 * Each piece is a `body`, filled with the person's color and outlined as one silhouette, and
 * optional `details` drawn on top in the outline's ink: eyes, pips, wheels' hubs.
 *
 * Nothing here but data and types, so a script can import it to draw them all for a look.
 */

import type { components } from '../../api/schema'

type Piece = components['schemas']['Piece']
type PieceColor = components['schemas']['PieceColor']

export type Shape =
  | readonly ['path', string]
  | readonly ['circle', number, number, number]
  | readonly ['ellipse', number, number, number, number]
  | readonly ['rect', number, number, number, number, number?]
  /** A stroked line, not filled. */
  | readonly ['line', string]

export interface PieceShape {
  label: string
  body: readonly Shape[]
  details?: readonly Shape[]
}

export const MEEPLE_PATH =
  'M50 6c-10.5 0-16.5 8-16.5 17 0 5 1.6 8.6 3.4 11C24 38.4 9 44 6.5 53.5 5 59.8 11.5 63 21 63.5 17 73 11.5 84 9 94h29c3-7.5 7-13.5 12-13.5S59 86.5 62 94h29c-2.5-10-8-21-12-30.5 9.5-.5 16-3.7 14.5-10C91 44 76 38.4 63.1 34c1.8-2.4 3.4-6 3.4-11C66.5 14 60.5 6 50 6z'

export const PIECES = {
  meeple: { label: 'Meeple', body: [['path', MEEPLE_PATH]] },
  pawn: {
    label: 'Pawn',
    body: [
      ['circle', 50, 22, 15],
      ['rect', 35, 37, 30, 8, 4],
      ['path', 'M41 44C41 58 35 70 28 82H72C65 70 59 58 59 44Z'],
      ['rect', 20, 80, 60, 13, 5],
    ],
  },
  cube: {
    label: 'Cube',
    body: [['path', 'M50 8L88 28V72L50 92L12 72V28Z']],
    details: [['line', 'M12 28L50 48L88 28M50 48V92']],
  },
  die: {
    label: 'Die',
    body: [['rect', 12, 12, 76, 76, 16]],
    details: [
      ['circle', 31, 31, 7],
      ['circle', 69, 31, 7],
      ['circle', 50, 50, 7],
      ['circle', 31, 69, 7],
      ['circle', 69, 69, 7],
    ],
  },
  rook: {
    label: 'Rook',
    body: [
      ['path', 'M24 8H36V18H44V8H56V18H64V8H76V36H24Z'],
      ['rect', 28, 34, 44, 9, 2],
      ['path', 'M34 42H66L70 80H30Z'],
      ['rect', 20, 79, 60, 14, 4],
    ],
    details: [['rect', 46, 52, 8, 16, 4]],
  },
  knight: {
    label: 'Knight',
    body: [
      [
        'path',
        'M32 74C32 62 38 54 46 48C38 50 28 54 21 51C16 49 15 43 18 38C24 28 34 20 42 15L43 6L51 13C67 13 80 28 80 48C80 60 76 68 73 74Z',
      ],
      ['rect', 26, 71, 52, 10, 3],
      ['rect', 20, 79, 62, 14, 4],
    ],
    details: [
      ['circle', 43, 28, 3.5],
      ['line', 'M56 20C64 26 68 36 68 48'],
    ],
  },
  crown: {
    label: 'Crown',
    body: [
      ['path', 'M10 30L30 52L50 18L70 52L90 30L82 78H18Z'],
      ['rect', 16, 74, 68, 14, 3],
      ['circle', 10, 28, 6],
      ['circle', 50, 15, 6],
      ['circle', 90, 28, 6],
    ],
    details: [
      ['circle', 32, 81, 3.5],
      ['circle', 50, 81, 3.5],
      ['circle', 68, 81, 3.5],
    ],
  },
  top_hat: {
    label: 'Top hat',
    body: [
      ['path', 'M28 76L30 20C30 12 70 12 70 20L72 76Z'],
      ['ellipse', 50, 78, 42, 11],
    ],
    details: [['path', 'M29.4 58H70.6L71.1 70H28.9Z']],
  },
  race_car: {
    label: 'Race car',
    body: [
      [
        'path',
        'M6 64C6 56 12 53 20 52L36 50C38 41 44 36 52 36H58C64 36 67 42 69 49L84 51C92 52 95 57 95 64V70H6Z',
      ],
      ['rect', 78, 36, 18, 6, 2],
      ['rect', 85, 40, 5, 14],
      ['circle', 26, 72, 13],
      ['circle', 76, 72, 13],
    ],
    details: [
      ['circle', 26, 72, 5],
      ['circle', 76, 72, 5],
      ['path', 'M44 49C46 44 49 42 53 42H57C60 42 62 45 63 49Z'],
    ],
  },
  dog: {
    label: 'Scottie dog',
    body: [
      [
        'path',
        'M7 46C7 40 11 36 17 34L19 16L28 29L32 18L36 33C40 38 45 40 53 40H78L86 22L91 26L87 42C91 46 93 52 91 60V86H79L76 68H47L44 86H32L30 67C24 67 18 63 14 57L9 55Z',
      ],
    ],
    details: [['circle', 22, 41, 3]],
  },
  thimble: {
    label: 'Thimble',
    body: [
      ['path', 'M28 80L32 24C33 10 67 10 68 24L72 80Z'],
      ['rect', 22, 76, 56, 15, 5],
    ],
    details: [
      ['circle', 42, 24, 2.6],
      ['circle', 58, 24, 2.6],
      ['circle', 50, 36, 2.6],
      ['circle', 38, 36, 2.6],
      ['circle', 62, 36, 2.6],
      ['circle', 44, 48, 2.6],
      ['circle', 56, 48, 2.6],
      ['circle', 34, 48, 2.6],
      ['circle', 66, 48, 2.6],
      ['circle', 38, 60, 2.6],
      ['circle', 50, 60, 2.6],
      ['circle', 62, 60, 2.6],
    ],
  },
  boot: {
    label: 'Boot',
    body: [
      ['rect', 22, 8, 40, 12, 3],
      ['path', 'M26 18H58V54C62 58 72 61 82 63C90 65 94 71 94 79V88H26Z'],
    ],
    details: [
      ['rect', 26, 82, 68, 6],
      ['line', 'M44 28H58M44 38H58M46 48H60'],
    ],
  },
  battleship: {
    label: 'Battleship',
    body: [
      ['path', 'M4 62H96L84 82H16Z'],
      ['rect', 32, 46, 36, 18, 2],
      ['rect', 40, 32, 16, 16, 2],
      ['rect', 60, 22, 7, 26, 1],
      ['rect', 16, 54, 14, 10, 2],
      ['rect', 70, 54, 14, 10, 2],
      ['rect', 6, 56, 14, 4, 2],
      ['rect', 80, 56, 14, 4, 2],
    ],
    details: [
      ['circle', 28, 71, 2.8],
      ['circle', 42, 71, 2.8],
      ['circle', 56, 71, 2.8],
      ['circle', 70, 71, 2.8],
      ['rect', 44, 36, 8, 5, 1],
    ],
  },
  iron: {
    label: 'Iron',
    body: [
      [
        'path',
        'M40 50C40 30 46 22 56 22H74C82 22 87 30 87 50H77C77 38 75 32 70 32H58C52 32 50 38 50 50Z',
      ],
      ['path', 'M6 82C8 64 24 50 48 48H90L93 82Z'],
    ],
    details: [['rect', 6, 76, 87, 6, 2]],
  },
  wheelbarrow: {
    label: 'Wheelbarrow',
    body: [
      ['path', 'M24 36H88L76 62H36Z'],
      ['path', 'M4 30L8 24L40 46L36 52Z'],
      ['rect', 36, 58, 7, 28, 2],
      ['rect', 66, 58, 6, 14, 2],
      ['circle', 70, 76, 14],
    ],
    details: [
      ['circle', 70, 76, 5],
      ['line', 'M38 44H78'],
    ],
  },
  cat: {
    label: 'Cat',
    body: [
      [
        'path',
        'M32 92C22 92 20 80 24 66C27 54 30 46 33 40C27 34 27 22 29 10L40 22H60L71 10C73 22 73 34 67 40C70 46 73 54 76 66C80 80 78 92 68 92Z',
      ],
      ['path', 'M66 88C80 89 86 82 86 70C86 64 94 64 94 70C94 86 84 95 66 93Z'],
    ],
    details: [
      ['ellipse', 42, 29, 3, 4.5],
      ['ellipse', 58, 29, 3, 4.5],
      ['path', 'M47 36H53L50 40Z'],
    ],
  },
  duck: {
    label: 'Rubber duck',
    body: [
      ['circle', 38, 34, 20],
      ['path', 'M20 34C10 32 4 36 4 40C10 44 18 44 22 42Z'],
      [
        'path',
        'M12 64C12 50 26 48 38 52C52 55 66 52 82 38C88 50 94 62 90 74C86 88 70 92 50 92C26 92 12 80 12 64Z',
      ],
    ],
    details: [
      ['circle', 42, 28, 4],
      ['line', 'M44 66C52 74 64 74 72 66'],
    ],
  },
  rocket: {
    label: 'Rocket',
    body: [
      ['path', 'M50 4C65 16 70 36 67 70H33C30 36 35 16 50 4Z'],
      ['path', 'M34 46L16 70V86L34 74Z'],
      ['path', 'M66 46L84 70V86L66 74Z'],
      ['rect', 38, 68, 24, 10, 3],
      ['path', 'M42 78H58L50 96Z'],
    ],
    details: [
      ['circle', 50, 36, 9],
      ['rect', 38, 68, 24, 4],
    ],
  },
} as const satisfies Record<Piece, PieceShape>

export type PieceName = keyof typeof PIECES

/** How the picker groups them. */
export const PIECE_GROUPS: { label: string; pieces: PieceName[] }[] = [
  { label: 'From the table', pieces: ['meeple', 'pawn', 'cube', 'die', 'rook', 'knight', 'crown'] },
  {
    label: 'Classic tokens',
    pieces: ['top_hat', 'race_car', 'dog', 'thimble', 'boot', 'battleship', 'iron', 'wheelbarrow'],
  },
  { label: 'Odds and ends', pieces: ['cat', 'duck', 'rocket'] },
]

export const PIECE_COLORS = {
  teal: { label: 'Teal', hex: '#1d7874' },
  coral: { label: 'Coral', hex: '#dd7373' },
  gold: { label: 'Gold', hex: '#c9a94b' },
  cream: { label: 'Cream', hex: '#fffaf3' },
  slate: { label: 'Slate', hex: '#8d91ac' },
  plum: { label: 'Plum', hex: '#9b6fa8' },
  leaf: { label: 'Leaf', hex: '#6fa86b' },
  sky: { label: 'Sky', hex: '#5b9bd5' },
  orange: { label: 'Orange', hex: '#e08a3c' },
} as const satisfies Record<PieceColor, { label: string; hex: string }>

export type PieceColorName = keyof typeof PIECE_COLORS
