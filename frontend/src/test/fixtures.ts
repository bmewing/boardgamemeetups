import type { UserProfile } from '../api/client'

type AchievementName = UserProfile['achievements'][number]['achievement']

// The backend's rewards (app/achievements.py), for building realistic profiles.
const PIECE_REWARDS = {
  thimble: 'add_game',
  rocket: 'import_collection',
  duck: 'can_teach',
  dog: 'make_friend',
  battleship: 'recruit',
  rook: 'start_group',
  top_hat: 'schedule_meetup',
  wheelbarrow: 'group_of_4',
  cat: 'join_group',
  race_car: 'rsvp_yes',
  knight: 'nominate_picked',
  boot: 'attend_1',
  iron: 'attend_5',
  crown: 'win_game',
} as const
const COLOR_REWARDS = {
  plum: 'rate_games',
  sky: 'stay_in_loop',
  leaf: 'friends_5',
  orange: 'recruit_attends',
  slate: 'joined_by_invite',
} as const
const ALL: AchievementName[] = [
  'add_game',
  'import_collection',
  'can_teach',
  'rate_games',
  'stay_in_loop',
  'make_friend',
  'friends_5',
  'recruit',
  'recruit_attends',
  'joined_by_invite',
  'start_group',
  'schedule_meetup',
  'group_of_4',
  'lock_pick',
  'log_night',
  'join_group',
  'rsvp_yes',
  'nominate_picked',
  'vote',
  'bring_game',
  'attend_1',
  'attend_5',
  'attend_20',
  'win_game',
  'coop_win',
]
const GOALS: Partial<Record<AchievementName, number>> = {
  rate_games: 10,
  friends_5: 5,
  group_of_4: 4,
  attend_1: 1,
  attend_5: 5,
  attend_20: 20,
}

/**
 * The achievements, pieces and colors of a profile that has earned these achievements
 * (`isNew` ones earned since they last looked).
 */
export function earnedProfile(
  earned: AchievementName[] = [],
  isNew: AchievementName[] = [],
): Pick<UserProfile, 'achievements' | 'pieces' | 'colors'> {
  const has = (a: AchievementName | null) => a === null || earned.includes(a)
  const pieceNames = ['meeple', 'pawn', 'cube', 'die', ...Object.keys(PIECE_REWARDS)] as const
  const colorNames = ['teal', 'coral', 'gold', 'cream', ...Object.keys(COLOR_REWARDS)] as const
  return {
    achievements: ALL.map((achievement) => ({
      achievement,
      earned_at: earned.includes(achievement) ? '2026-11-08T12:00:00Z' : null,
      new: isNew.includes(achievement),
      progress:
        GOALS[achievement] === undefined
          ? null
          : earned.includes(achievement)
            ? GOALS[achievement]!
            : 0,
      goal: GOALS[achievement] ?? null,
    })),
    pieces: pieceNames.map((piece) => {
      const by = (PIECE_REWARDS as Record<string, AchievementName>)[piece] ?? null
      return {
        piece: piece as UserProfile['pieces'][number]['piece'],
        unlocked_by: by,
        unlocked: has(by),
      }
    }),
    colors: colorNames.map((color) => {
      const by = (COLOR_REWARDS as Record<string, AchievementName>)[color] ?? null
      return {
        color: color as UserProfile['colors'][number]['color'],
        unlocked_by: by,
        unlocked: has(by),
      }
    }),
  }
}

export const profile: UserProfile = {
  id: '0190f0e2-0000-7000-8000-000000000001',
  email: 'sam@example.com',
  display_name: 'Sam',
  avatar_url: null,
  piece: null,
  piece_color: null,
  time_zone: 'UTC',
  discord_username: null,
  bgg_username: null,
  bgg_pulled_at: null,
  bga_username: null,
  bga_premium: false,
  collection_visibility: 'friends',
  email_opt_outs: [],
  is_admin: false,
  ...earnedProfile(),
}
