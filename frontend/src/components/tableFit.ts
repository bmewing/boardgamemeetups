export type TableFit = 'together' | 'split'

const seats = (min: number, max: number, players: number) => min <= players && players <= max

/**
 * How a game fits a headcount, the same rule the API uses for a meetup's games: one table
 * of everyone, or (when the group is willing to split) a table of 2 to n−2 so nobody is
 * left on their own. Null when it doesn't fit or its player count isn't known.
 */
export function tableFit(
  minPlayers: number | null,
  maxPlayers: number | null,
  players: number,
  willingToSplit: boolean,
): TableFit | null {
  if (maxPlayers === null || players < 1) return null
  const low = minPlayers ?? 1
  if (seats(low, maxPlayers, players)) return 'together'
  if (willingToSplit) {
    for (let t = 2; t <= players - 2; t++) if (seats(low, maxPlayers, t)) return 'split'
  }
  return null
}

export interface CapacityNote {
  text: string
  color: 'red' | 'yellow' | 'gray'
}

/**
 * Why a game on the ballot is a squeeze for the people going, or null when everyone fits
 * at one table. Too many or too few is red; too many but splittable is yellow, since it
 * still works as one of several tables.
 */
export function capacityNote(
  minPlayers: number | null,
  maxPlayers: number | null,
  fit: TableFit | null,
  headcount: number,
): CapacityNote | null {
  if (fit === 'together' || headcount < 1) return null
  if (maxPlayers === null) return { text: 'Player count unknown', color: 'gray' }
  if (headcount > maxPlayers) {
    return fit === 'split'
      ? {
          text: `Seats up to ${maxPlayers}: ${headcount} going means splitting up`,
          color: 'yellow',
        }
      : { text: `Too many: seats up to ${maxPlayers}, ${headcount} going`, color: 'red' }
  }
  return { text: `Too few: needs ${minPlayers ?? 1}, ${headcount} going`, color: 'red' }
}
