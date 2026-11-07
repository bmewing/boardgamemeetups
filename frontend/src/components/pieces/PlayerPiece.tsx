import { createElement, type CSSProperties } from 'react'

import { palette } from '../../theme'
import { pieceDrawing, type Shape } from './drawings'
import { type PieceHolder, pieceOf } from './pieceOf'
import { PIECE_COLORS, PIECE_LABELS, type PieceColorName, type PieceName } from './shapes'

const INK = palette.olive

function draw(shape: Shape, key: number) {
  return createElement(shape.tag, { key, ...shape.attrs })
}

type DrawingProps = {
  piece: PieceName
  color: PieceColorName
  size?: number
  /** Read out instead of the piece's name; empty to hide it from screen readers. */
  label?: string
  className?: string
  style?: CSSProperties
}

/** One piece in one color. The body is outlined as a single silhouette, then filled. */
export function PieceDrawing({ piece, color, size = 38, label, className, style }: DrawingProps) {
  const { body, details, lines } = pieceDrawing(piece)
  const name = label ?? `${PIECE_COLORS[color].label} ${PIECE_LABELS[piece].toLowerCase()}`
  return (
    <svg
      viewBox="0 0 100 100"
      width={size}
      height={size}
      className={className}
      style={{ flexShrink: 0, overflow: 'visible', ...style }}
      role={name ? 'img' : undefined}
      aria-label={name || undefined}
      aria-hidden={name ? undefined : true}
    >
      <g fill={INK} stroke={INK} strokeWidth={10} strokeLinejoin="round">
        {body.map(draw)}
      </g>
      <g fill={PIECE_COLORS[color].hex}>{body.map(draw)}</g>
      <g fill={INK}>{details.map(draw)}</g>
      <g fill="none" stroke={INK} strokeWidth={5} strokeLinecap="round" strokeLinejoin="round">
        {lines.map(draw)}
      </g>
    </svg>
  )
}

/** The piece that stands for someone. Labelled with their name unless `label` says otherwise. */
export function PlayerPiece({
  person,
  name,
  label,
  ...props
}: Omit<DrawingProps, 'piece' | 'color'> & { person: PieceHolder; name?: string }) {
  const { piece, color } = pieceOf(person)
  return <PieceDrawing piece={piece} color={color} label={label ?? name} {...props} />
}
