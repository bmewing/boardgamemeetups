/**
 * The game pieces people pick to stand for them, and the colors they come in. The names
 * match the backend's (app/pieces.py); each piece is drawn from svg/<name>.svg (drawings.ts).
 */

import type { components } from '../../api/schema'

type Piece = components['schemas']['Piece']
type PieceColor = components['schemas']['PieceColor']

/** What each piece is called on screen. One entry per backend name, or the build fails. */
export const PIECE_LABELS = {
  meeple: 'Meeple',
  pawn: 'Pawn',
  cube: 'Cube',
  die: 'Die',
  rook: 'Rook',
  knight: 'Knight',
  crown: 'Crown',
  top_hat: 'Top hat',
  race_car: 'Race car',
  dog: 'Scottie dog',
  thimble: 'Thimble',
  boot: 'Boot',
  battleship: 'Battleship',
  iron: 'Iron',
  wheelbarrow: 'Wheelbarrow',
  cat: 'Cat',
  duck: 'Rubber duck',
  rocket: 'Rocket',
} as const satisfies Record<Piece, string>

export type PieceName = keyof typeof PIECE_LABELS

/** How the picker groups them. A piece left out of every group can't be picked. */
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
