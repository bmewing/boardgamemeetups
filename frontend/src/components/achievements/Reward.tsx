import { pieceOf, type PieceHolder } from '../pieces/pieceOf'
import { PieceDrawing } from '../pieces/PlayerPiece'
import { PIECE_COLORS } from '../pieces/shapes'
import classes from './achievements.module.css'
import { LockBadge } from './LockBadge'
import type { Reward as RewardValue } from './rewards'

/** A picture of what an achievement gives: the piece in your color, the color, or a medal. */
export function Reward({
  reward,
  holder,
  earned,
  size = 36,
}: {
  reward: RewardValue
  holder: PieceHolder
  earned: boolean
  size?: number
}) {
  const faded = earned ? undefined : classes.unearned
  return (
    <span className={classes.reward} style={{ width: size, height: size }}>
      {reward.kind === 'piece' && (
        <PieceDrawing
          piece={reward.piece}
          color={pieceOf(holder).color}
          size={size}
          label=""
          className={faded}
        />
      )}
      {reward.kind === 'color' && (
        <span
          className={`${classes.swatch} ${faded ?? ''}`}
          style={{ background: PIECE_COLORS[reward.color].hex }}
        />
      )}
      {reward.kind === 'badge' && <Medal className={faded} />}
      {!earned && <LockBadge />}
    </span>
  )
}

function Medal({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 40" className={`${classes.medal} ${className ?? ''}`} aria-hidden>
      <path d="M13 3h6l3 12h-6zM27 3h-6l-3 12h6z" fill="var(--bgg-coral)" />
      <circle
        cx={20}
        cy={25}
        r={11}
        fill={PIECE_COLORS.gold.hex}
        stroke="var(--bgg-ink)"
        strokeWidth={2.5}
      />
      <path
        d="M20 18.5l2 4.2 4.5.5-3.4 3 1 4.5-4.1-2.4-4.1 2.4 1-4.5-3.4-3 4.5-.5z"
        fill="var(--bgg-ink)"
      />
    </svg>
  )
}
