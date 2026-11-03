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
