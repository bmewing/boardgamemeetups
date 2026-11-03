import type { FieldName, Ownership, UserGame } from '../api/collection'
import type { GameSummary } from '../api/games'

export const FIELD_LABELS: Record<FieldName, string> = {
  ownership: 'Ownership',
  wishlist_priority: 'Wishlist',
  want_to_play: 'Want to play',
  rating: 'Your rating',
  weight_vote: 'Your weight',
  playtime_feel: 'Length',
  can_teach: 'Can teach',
  teach_minutes: 'Teach time',
  plays: 'Plays',
  will_bring: 'Will bring',
  notes: 'Notes',
}

export const OWNERSHIP_LABELS: Record<Ownership, string> = {
  owned: 'Owned',
  preordered: 'Preordered',
  previously_owned: 'Previously owned',
}

// BGG's own wording for wishlist priorities.
export const WISHLIST_LABELS: Record<number, string> = {
  1: 'Must have',
  2: 'Love to have',
  3: 'Like to have',
  4: 'Thinking about it',
  5: "Don't buy this",
}

const PLAYTIME_LABELS: Record<string, string> = {
  shorter: 'Shorter than listed',
  just_right: 'About as listed',
  longer: 'Longer than listed',
}

/** A field's value as a person would say it; "—" for no answer. */
export function formatValue(field: FieldName, value: unknown): string {
  if (value === null || value === undefined) return '—'
  switch (field) {
    case 'ownership':
      return OWNERSHIP_LABELS[value as Ownership] ?? String(value)
    case 'wishlist_priority':
      return WISHLIST_LABELS[value as number] ?? String(value)
    case 'playtime_feel':
      return PLAYTIME_LABELS[value as string] ?? String(value)
    case 'teach_minutes':
      return `${value} min`
    case 'want_to_play':
    case 'can_teach':
    case 'will_bring':
      return value ? 'Yes' : 'No'
    case 'notes': {
      const text = String(value)
      return text.length > 60 ? `“${text.slice(0, 57)}…”` : `“${text}”`
    }
    default:
      return String(value)
  }
}

export function isOwned(row: Pick<UserGame, 'ownership'>): boolean {
  return row.ownership === 'owned' || row.ownership === 'preordered'
}

export function isWanted(row: Pick<UserGame, 'wishlist_priority' | 'want_to_play'>): boolean {
  return row.wishlist_priority !== null || row.want_to_play
}

/**
 * The expansions in `rows` that belong to `game`, to offer removing along with it. An
 * expansion that also fits another base game still in the list stays out of this.
 */
export function expansionsInList(game: GameSummary, rows: UserGame[]): GameSummary[] {
  if (game.is_expansion) return []
  const listed = new Set(rows.map((r) => r.game.id))
  return rows
    .map((r) => r.game)
    .filter(
      (g) =>
        g.is_expansion &&
        g.base_game_ids.includes(game.id) &&
        !g.base_game_ids.some((id) => id !== game.id && listed.has(id)),
    )
}
