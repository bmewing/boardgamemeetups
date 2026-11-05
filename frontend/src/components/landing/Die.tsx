import { useState, type CSSProperties } from 'react'

import classes from './Die.module.css'

// Which cells of a 3 × 3 grid hold a pip, per face.
const PIPS: Record<number, number[]> = {
  1: [4],
  2: [0, 8],
  3: [0, 4, 8],
  4: [0, 2, 6, 8],
  5: [0, 2, 4, 6, 8],
  6: [0, 2, 3, 5, 6, 8],
}

// Where each face sits on the cube, and the cube rotation [x, y] that turns it to the front.
const FACES: { face: number; place: string; show: [number, number] }[] = [
  { face: 1, place: 'rotateY(0deg)', show: [0, 0] },
  { face: 2, place: 'rotateY(90deg)', show: [0, -90] },
  { face: 3, place: 'rotateX(90deg)', show: [-90, 0] },
  { face: 4, place: 'rotateX(-90deg)', show: [90, 0] },
  { face: 5, place: 'rotateY(-90deg)', show: [0, 90] },
  { face: 6, place: 'rotateY(180deg)', show: [0, 180] },
]

/** Land on a random face after one or two extra full turns, so it always visibly tumbles. */
function tumble(prev: { turns: number }) {
  return {
    face: 1 + Math.floor(Math.random() * 6),
    turns: prev.turns + 1 + Math.floor(Math.random() * 2),
  }
}

type DieProps = {
  /** Edge length in px. */
  size?: number
  /** Change this to roll the die from outside (the demo does, each round). */
  rollKey?: number
  tone?: 'cream' | 'coral'
}

/** A 3D die that tumbles when hovered or tapped and lands on a random face. */
export function Die({ size = 56, rollKey, tone = 'cream' }: DieProps) {
  const [{ face, turns }, setRoll] = useState({ face: 5, turns: 0 })
  const [lastKey, setLastKey] = useState(rollKey)

  const roll = () => setRoll(tumble)

  // A new rollKey rolls the die: adjusted while rendering, React's pattern for following a prop.
  if (rollKey !== lastKey) {
    setLastKey(rollKey)
    if (rollKey !== undefined) setRoll(tumble)
  }

  const [x, y] = FACES[face - 1].show
  const style = {
    '--die-size': `${size}px`,
    '--die-x': `${x + 360 * turns}deg`,
    '--die-y': `${y + 360 * turns}deg`,
  } as CSSProperties

  return (
    <button
      type="button"
      className={classes.die}
      data-tone={tone}
      style={style}
      onClick={roll}
      onMouseEnter={roll}
      aria-label={`Roll the die (showing ${face})`}
    >
      <span className={classes.tilt}>
        <span className={classes.cube}>
          {FACES.map((f) => (
            <span
              key={f.face}
              className={classes.face}
              style={{ transform: `${f.place} translateZ(calc(var(--die-size) / 2))` }}
            >
              {Array.from({ length: 9 }, (_, i) => (
                <span key={i} className={PIPS[f.face].includes(i) ? classes.pip : undefined} />
              ))}
            </span>
          ))}
        </span>
      </span>
    </button>
  )
}
