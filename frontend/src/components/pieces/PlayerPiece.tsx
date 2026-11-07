import { createElement, type CSSProperties } from 'react'

import { palette } from '../../theme'
import { type PieceHolder, pieceOf } from './pieceOf'
import { PIECE_COLORS, PIECES, type PieceColorName, type PieceName, type Shape } from './shapes'

const INK = palette.olive

function draw(shape: Shape, key: number) {
  switch (shape[0]) {
    case 'path':
    case 'line':
      return createElement('path', { key, d: shape[1] })
    case 'circle':
      return createElement('circle', { key, cx: shape[1], cy: shape[2], r: shape[3] })
    case 'ellipse':
      return createElement('ellipse', {
        key,
        cx: shape[1],
        cy: shape[2],
        rx: shape[3],
        ry: shape[4],
      })
    case 'rect':
      return createElement('rect', {
        key,
        x: shape[1],
        y: shape[2],
        width: shape[3],
        height: shape[4],
        rx: shape[5] ?? 0,
      })
  }
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
  const shape = PIECES[piece]
  const body = shape.body.map(draw)
  const details: readonly Shape[] = 'details' in shape ? shape.details : []
  const name = label ?? `${PIECE_COLORS[color].label} ${shape.label.toLowerCase()}`
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
        {body}
      </g>
      <g fill={PIECE_COLORS[color].hex}>{shape.body.map(draw)}</g>
      <g fill={INK}>{details.filter((d) => d[0] !== 'line').map(draw)}</g>
      <g fill="none" stroke={INK} strokeWidth={5} strokeLinecap="round" strokeLinejoin="round">
        {details.filter((d) => d[0] === 'line').map(draw)}
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
