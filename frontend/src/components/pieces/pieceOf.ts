import { PIECE_COLORS, type PieceColorName, type PieceName } from './shapes'

const COLOR_NAMES = Object.keys(PIECE_COLORS) as PieceColorName[]

/** Anyone with a piece, or who may have one: a person, a profile, an admin's user row. */
export interface PieceHolder {
  id: string
  piece?: PieceName | null
  piece_color?: PieceColorName | null
}

/** Someone who hasn't picked gets a meeple in a color that's always the same for them. */
export function defaultColor(id: string): PieceColorName {
  let hash = 0
  for (const char of id) hash = (hash * 31 + char.charCodeAt(0)) | 0
  return COLOR_NAMES[Math.abs(hash) % COLOR_NAMES.length]
}

export function pieceOf(holder: PieceHolder): { piece: PieceName; color: PieceColorName } {
  return {
    piece: holder.piece ?? 'meeple',
    color: holder.piece_color ?? defaultColor(holder.id),
  }
}
