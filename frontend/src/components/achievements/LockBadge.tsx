import classes from './achievements.module.css'

/** A small padlock, drawn in the corner of something still locked. */
export function LockBadge() {
  return (
    <svg viewBox="0 0 16 16" width={16} height={16} className={classes.lock} aria-hidden>
      <path
        d="M4.5 7V5a3.5 3.5 0 0 1 7 0v2"
        fill="none"
        stroke="currentColor"
        strokeWidth={2}
        strokeLinecap="round"
      />
      <rect x={2.5} y={7} width={11} height={8} rx={2} fill="currentColor" />
    </svg>
  )
}
