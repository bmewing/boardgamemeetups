import type { components } from '../api/schema'

export type GroupRollup = components['schemas']['RollupRead']
export type Reason = components['schemas']['ReasonRead']

/** "About 70 min, plus 10 to teach": shown to help the vote, never used to rank. */
export function lengthLabel(rollup: GroupRollup): string | null {
  if (rollup.length_minutes === null) return null
  const teach = rollup.teach_minutes ? `, plus ${rollup.teach_minutes} to teach` : ''
  return `About ${rollup.length_minutes} min${teach}`
}
