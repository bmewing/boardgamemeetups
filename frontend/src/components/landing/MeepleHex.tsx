import { palette } from '../../theme'
import { MEEPLE_PATH } from './Meeple'
import classes from './MeepleHex.module.css'

/** The favicon art, large: three meeples in a hex tile, bobbing gently. */
export function MeepleHex({ size = 320 }: { size?: number }) {
  return (
    <svg
      viewBox="0 0 240 240"
      width={size}
      height={size}
      className={classes.hex}
      role="img"
      aria-label="Three meeples standing together in a hexagon tile"
    >
      <path
        d="M120 6l100 58v116l-100 58-100-58V64z"
        className={classes.tile}
        stroke={palette.olive}
        strokeWidth={9}
        strokeLinejoin="round"
      />
      <g className={classes.left}>
        <path d={MEEPLE_PATH} fill={palette.coral} transform="translate(20 62) scale(0.86)" />
      </g>
      <g className={classes.right}>
        <path d={MEEPLE_PATH} fill={palette.navy} transform="translate(134 62) scale(0.86)" />
      </g>
      <g className={classes.middle}>
        <path
          d={MEEPLE_PATH}
          fill={palette.teal}
          stroke={palette.olive}
          strokeWidth={4}
          strokeLinejoin="round"
          transform="translate(66 78) scale(1.08)"
        />
      </g>
    </svg>
  )
}
