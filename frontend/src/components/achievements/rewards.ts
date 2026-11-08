import type { UserProfile } from '../../api/client'
import {
  ACHIEVEMENTS,
  type AchievementName,
  type ChapterName,
  NEXT_UP_ORDER,
  PIECE_COLORS,
  PIECE_LABELS,
  type PieceColorName,
  type PieceName,
} from '../pieces/shapes'

export type Standing = UserProfile['achievements'][number] & { achievement: AchievementName }

/** What an achievement unlocks: a piece, a color, or nothing but the badge itself. */
export type Reward =
  { kind: 'piece'; piece: PieceName } | { kind: 'color'; color: PieceColorName } | { kind: 'badge' }

export function rewardOf(profile: UserProfile, achievement: AchievementName): Reward {
  const piece = profile.pieces.find((p) => p.unlocked_by === achievement)
  if (piece) return { kind: 'piece', piece: piece.piece }
  const color = profile.colors.find((c) => c.unlocked_by === achievement)
  if (color) return { kind: 'color', color: color.color }
  return { kind: 'badge' }
}

/** "the rook", "the sky color", or null for a badge. */
export function rewardName(reward: Reward): string | null {
  if (reward.kind === 'piece') return `the ${PIECE_LABELS[reward.piece].toLowerCase()}`
  if (reward.kind === 'color') return `the ${PIECE_COLORS[reward.color].label.toLowerCase()} color`
  return null
}

export function isEarned(standing: Standing | undefined): boolean {
  return Boolean(standing?.earned_at)
}

export function standingsOf(profile: UserProfile): Map<AchievementName, Standing> {
  return new Map(profile.achievements.map((a) => [a.achievement, a]))
}

export function inChapter(profile: UserProfile, chapter: ChapterName): Standing[] {
  return profile.achievements.filter((a) => ACHIEVEMENTS[a.achievement].chapter === chapter)
}

/** The first achievement on the suggested path they haven't earned, skipped or been ruled out of. */
export function nextAchievement(
  profile: UserProfile,
  ruledOut: AchievementName[] = [],
): AchievementName | null {
  const standings = standingsOf(profile)
  return (
    NEXT_UP_ORDER.find((name) => !isEarned(standings.get(name)) && !ruledOut.includes(name)) ?? null
  )
}
