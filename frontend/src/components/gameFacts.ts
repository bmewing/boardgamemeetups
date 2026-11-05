import type { GameSummary } from '../api/games'

function range(min: number | null, max: number | null): string | null {
  if (min && max) return min === max ? `${min}` : `${min}–${max}`
  return (min ?? max)?.toString() ?? null
}

export function playersLabel(game: GameSummary): string | null {
  const players = range(game.min_players, game.max_players)
  if (!players) return null
  return `${players} ${players === '1' ? 'player' : 'players'}`
}

type Players = Pick<GameSummary, 'min_players' | 'max_players'>

/**
 * A base game's player range widened by expansions for it, the same rule the API uses: the
 * lowest minimum and highest maximum of them all. Unknown while the base game's maximum is.
 */
export function playerRange(game: Players, expansions: Players[]): Players {
  const all = [game, ...expansions]
  const lows = all.map((g) => g.min_players).filter((n): n is number => n !== null)
  const highs = all.map((g) => g.max_players).filter((n): n is number => n !== null)
  return {
    min_players: lows.length ? Math.min(...lows) : null,
    max_players: game.max_players === null ? null : Math.max(...highs),
  }
}

/** "seats 1–6" when expansions change the game's player range; null when they don't. */
export function widenedLabel(game: Players, widened: Players): string | null {
  if (widened.min_players === game.min_players && widened.max_players === game.max_players) {
    return null
  }
  return `seats ${range(widened.min_players, widened.max_players)}`
}

export function playtimeLabel(game: GameSummary): string | null {
  const minutes = range(game.min_playtime, game.max_playtime)
  return minutes ? `${minutes} min` : null
}

export function weightLabel(game: GameSummary): string | null {
  return game.weight ? `Weight ${game.weight.toFixed(1)}/5` : null
}

/** "Best at 3" or "Best at 3, 4". */
export function bestWithLabel(game: GameSummary): string | null {
  return game.best_with.length ? `Best at ${game.best_with.join(', ')}` : null
}
