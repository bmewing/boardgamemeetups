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
