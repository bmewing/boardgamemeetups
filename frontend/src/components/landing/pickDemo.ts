import { palette } from '../../theme'

// A make-believe meetup that plays itself on a loop: RSVPs come in, everyone's games pool,
// the ones that don't fit the headcount drop out, the table votes, and a pick is crowned.

export const PLAYERS = [
  { name: 'Ana', color: palette.coral },
  { name: 'Ben', color: palette.navy },
  { name: 'Cy', color: palette.teal },
  { name: 'Dot', color: '#c9a94b' },
  { name: 'Eli', color: '#fffaf3' },
]
export const HEADCOUNT = PLAYERS.length

/** Games the demo deals from. Edit freely; min/max are player counts. */
const GAMES = [
  { name: 'Wingspan', min: 1, max: 5 },
  { name: 'Catan', min: 3, max: 4 },
  { name: 'Codenames', min: 2, max: 8 },
  { name: 'Azul', min: 2, max: 4 },
  { name: 'Cascadia', min: 1, max: 4 },
  { name: 'Ticket to Ride', min: 2, max: 5 },
  { name: 'Just One', min: 3, max: 7 },
  { name: 'Splendor', min: 2, max: 4 },
  { name: 'Heat', min: 1, max: 6 },
  { name: 'Sushi Go Party!', min: 2, max: 8 },
  { name: 'The Crew', min: 2, max: 5 },
  { name: 'Patchwork', min: 2, max: 2 },
  { name: '7 Wonders', min: 3, max: 7 },
  { name: 'Root', min: 2, max: 4 },
  { name: 'Wavelength', min: 2, max: 12 },
  { name: 'Quacks', min: 2, max: 4 },
]
const DEALT = 7

export type Row = {
  name: string
  min: number
  max: number
  owner: number
  fits: boolean
  votes: number
}

export type Phase = 'rsvp' | 'pool' | 'fit' | 'vote' | 'pick'

/** One moment of the demo: `n` counts how far into the phase it is. */
export type Game = { round: number; rows: Row[]; phase: Phase; n: number }

export const LABELS: Record<Phase, string> = {
  rsvp: 'RSVPs coming in',
  pool: "Pooling everyone's shelves",
  fit: `Checking what fits ${HEADCOUNT}`,
  vote: 'Everyone votes',
  pick: "Tonight's pick",
}

function shuffle<T>(items: T[]): T[] {
  const out = [...items]
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[out[i], out[j]] = [out[j], out[i]]
  }
  return out
}

/** A fresh hand of games: at least three that fit and two that don't, each with distinct votes. */
export function dealRound(): Row[] {
  for (;;) {
    const games = shuffle(GAMES).slice(0, DEALT)
    const fitting = games.filter((g) => g.min <= HEADCOUNT && HEADCOUNT <= g.max).length
    if (fitting < 3 || DEALT - fitting < 2) continue
    const votes = shuffle([5, 4, 3, 2, 1, 0])
    let v = 0
    return games.map((g, i) => {
      const fits = g.min <= HEADCOUNT && HEADCOUNT <= g.max
      return { ...g, owner: i % HEADCOUNT, fits, votes: fits ? votes[v++] : 0 }
    })
  }
}

/** The step after `game`, and how long to show `game` before taking it. */
export function nextGame(game: Game, deal: () => Row[] = dealRound): [Game, number] {
  const { phase, n, rows } = game
  switch (phase) {
    case 'rsvp':
      return n < HEADCOUNT ? [{ ...game, n: n + 1 }, 380] : [{ ...game, phase: 'pool', n: 0 }, 500]
    case 'pool':
      return n < rows.length ? [{ ...game, n: n + 1 }, 260] : [{ ...game, phase: 'fit', n: 0 }, 600]
    case 'fit':
      return n < rows.length
        ? [{ ...game, n: n + 1 }, 300]
        : [{ ...game, phase: 'vote', n: 0 }, 900]
    case 'vote':
      return [{ ...game, phase: 'pick', n: 0 }, 1900]
    case 'pick':
      return [{ round: game.round + 1, rows: deal(), phase: 'rsvp', n: 0 }, 3600]
  }
}

/** Survivors ordered by votes, most first. */
export function ranking(rows: Row[]) {
  return rows
    .map((row, i) => ({ row, i }))
    .filter(({ row }) => row.fits)
    .sort((a, b) => b.row.votes - a.row.votes)
    .map(({ i }) => i)
}
