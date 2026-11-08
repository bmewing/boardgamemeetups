/**
 * The game pieces people pick to stand for them, and the colors they come in. The names
 * match the backend's (app/pieces.py); each piece is drawn from svg/<name>.svg (drawings.ts).
 */

import type { components } from '../../api/schema'

type Piece = components['schemas']['Piece']
type PieceColor = components['schemas']['PieceColor']
type Achievement = components['schemas']['Achievement']

/** What each piece is called on screen. One entry per backend name, or the build fails. */
export const PIECE_LABELS = {
  meeple: 'Meeple',
  pawn: 'Pawn',
  cube: 'Cube',
  die: 'Die',
  rook: 'Rook',
  knight: 'Knight',
  crown: 'Crown',
  top_hat: 'Top hat',
  race_car: 'Race car',
  dog: 'Scottie dog',
  thimble: 'Thimble',
  boot: 'Boot',
  battleship: 'Battleship',
  iron: 'Iron',
  wheelbarrow: 'Wheelbarrow',
  cat: 'Cat',
  duck: 'Rubber duck',
  rocket: 'Rocket',
} as const satisfies Record<Piece, string>

export type PieceName = keyof typeof PIECE_LABELS

/** How the picker groups them. A piece left out of every group can't be picked. */
export const PIECE_GROUPS: { label: string; pieces: PieceName[] }[] = [
  { label: 'From the table', pieces: ['meeple', 'pawn', 'cube', 'die', 'rook', 'knight', 'crown'] },
  {
    label: 'Classic tokens',
    pieces: ['top_hat', 'race_car', 'dog', 'thimble', 'boot', 'battleship', 'iron', 'wheelbarrow'],
  },
  { label: 'Odds and ends', pieces: ['cat', 'duck', 'rocket'] },
]

export const PIECE_COLORS = {
  teal: { label: 'Teal', hex: '#1d7874' },
  coral: { label: 'Coral', hex: '#dd7373' },
  gold: { label: 'Gold', hex: '#c9a94b' },
  cream: { label: 'Cream', hex: '#fffaf3' },
  slate: { label: 'Slate', hex: '#8d91ac' },
  plum: { label: 'Plum', hex: '#9b6fa8' },
  leaf: { label: 'Leaf', hex: '#6fa86b' },
  sky: { label: 'Sky', hex: '#5b9bd5' },
  orange: { label: 'Orange', hex: '#e08a3c' },
} as const satisfies Record<PieceColor, { label: string; hex: string }>

export type PieceColorName = keyof typeof PIECE_COLORS

/** The chapters achievements are shown in, following how someone grows into the site. */
export const CHAPTERS = {
  setup: { label: 'Getting set up', blurb: 'Make your list useful.' },
  growth: { label: 'Bringing people in', blurb: 'Game night is better with more players.' },
  running: { label: 'Running a group', blurb: 'Keep game night on the calendar.' },
  table: { label: 'At the table', blurb: 'Show up, pick, play.' },
} as const

export type ChapterName = keyof typeof CHAPTERS

type AchievementInfo = {
  chapter: ChapterName
  title: string
  /** What to do, said as an instruction. */
  how: string
  /** Where to go to do it. */
  to: string
  /** The button that goes there. */
  action: string
}

/**
 * What each achievement is called, which chapter it's in and how to earn it. What it
 * unlocks comes from the API. Listed in the backend's order (app/pieces.py), which keeps
 * each chapter together. One entry per backend name, or the build fails.
 */
export const ACHIEVEMENTS = {
  add_game: {
    chapter: 'setup',
    title: 'First on the shelf',
    how: 'Add a game to your list',
    to: '/games',
    action: 'Find a game',
  },
  import_collection: {
    chapter: 'setup',
    title: 'Liftoff',
    how: 'Import your collection from BGG or a file',
    to: '/collection',
    action: 'Import games',
  },
  can_teach: {
    chapter: 'setup',
    title: 'Rubber duck',
    how: 'Mark a game you can teach',
    to: '/collection',
    action: 'Open my games',
  },
  rate_games: {
    chapter: 'setup',
    title: 'Critic',
    how: 'Rate 10 of your games',
    to: '/collection',
    action: 'Rate games',
  },
  stay_in_loop: {
    chapter: 'setup',
    title: 'In the loop',
    how: 'Link Discord or subscribe to the calendar feed',
    to: '/groups',
    action: 'Get the calendar feed',
  },
  make_friend: {
    chapter: 'growth',
    title: 'Player two',
    how: 'Make a friend',
    to: '/friends',
    action: 'Find friends',
  },
  friends_5: {
    chapter: 'growth',
    title: 'Full table',
    how: 'Have 5 friends',
    to: '/friends',
    action: 'Find friends',
  },
  recruit: {
    chapter: 'growth',
    title: 'Recruiter',
    how: 'Bring someone new to the site with an invite',
    to: '/friends',
    action: 'Make an invite link',
  },
  recruit_attends: {
    chapter: 'growth',
    title: 'Talent scout',
    how: 'Someone you brought in comes to a game night',
    to: '/friends',
    action: 'Make an invite link',
  },
  joined_by_invite: {
    chapter: 'growth',
    title: 'Plus one',
    how: "Join through someone's invite",
    to: '/groups',
    action: 'See invites',
  },
  start_group: {
    chapter: 'running',
    title: 'Founder',
    how: 'Start a group',
    to: '/groups',
    action: 'Start a group',
  },
  schedule_meetup: {
    chapter: 'running',
    title: 'Host',
    how: 'Schedule a game night',
    to: '/groups',
    action: 'Pick a group',
  },
  group_of_4: {
    chapter: 'running',
    title: 'Quorum',
    how: 'Have 4 people in a group you run',
    to: '/groups',
    action: 'Invite people',
  },
  lock_pick: {
    chapter: 'running',
    title: 'Decider',
    how: 'Lock in the pick for a game night',
    to: '/groups',
    action: 'Go to your groups',
  },
  log_night: {
    chapter: 'running',
    title: 'Scorekeeper',
    how: 'Log what was played at a game night',
    to: '/groups',
    action: 'Go to your groups',
  },
  join_group: {
    chapter: 'table',
    title: 'Pulled up a chair',
    how: "Join someone else's group",
    to: '/groups',
    action: 'See invites',
  },
  rsvp_yes: {
    chapter: 'table',
    title: 'Count me in',
    how: 'Say yes to a game night',
    to: '/groups',
    action: 'See game nights',
  },
  nominate_picked: {
    chapter: 'table',
    title: 'Champion',
    how: 'Put forward a game that gets picked',
    to: '/groups',
    action: 'See game nights',
  },
  vote: {
    chapter: 'table',
    title: 'Ballot cast',
    how: 'Vote for a game someone else put forward',
    to: '/groups',
    action: 'See game nights',
  },
  bring_game: {
    chapter: 'table',
    title: 'Pack mule',
    how: 'Bring a game to a game night',
    to: '/groups',
    action: 'See game nights',
  },
  attend_1: {
    chapter: 'table',
    title: 'Boots on the ground',
    how: 'Come to a game night',
    to: '/groups',
    action: 'See game nights',
  },
  attend_5: {
    chapter: 'table',
    title: 'Regular',
    how: 'Come to 5 game nights',
    to: '/groups',
    action: 'See game nights',
  },
  attend_20: {
    chapter: 'table',
    title: 'Fixture',
    how: 'Come to 20 game nights',
    to: '/groups',
    action: 'See game nights',
  },
  win_game: {
    chapter: 'table',
    title: 'Victory!',
    how: 'Win a game',
    to: '/groups',
    action: 'See game nights',
  },
  coop_win: {
    chapter: 'table',
    title: 'Team player',
    how: 'Win a co-op game together',
    to: '/groups',
    action: 'See game nights',
  },
} as const satisfies Record<Achievement, AchievementInfo>

export type AchievementName = keyof typeof ACHIEVEMENTS

/**
 * The order to suggest achievements in on the home page: a path through the site, from
 * your own list to bringing friends to running game nights. Anything not here isn't
 * suggested (it comes with time, like winning).
 */
export const NEXT_UP_ORDER: AchievementName[] = [
  'add_game',
  'make_friend',
  'join_group',
  'start_group',
  'rsvp_yes',
  'schedule_meetup',
  'recruit',
  'import_collection',
  'can_teach',
  'stay_in_loop',
  'group_of_4',
  'rate_games',
  'friends_5',
]
