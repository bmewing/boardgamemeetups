import { Badge, Group, Text } from '@mantine/core'

import { type GroupRollup, lengthLabel, type Reason } from './rollupFormat'

const TONE_COLORS = { good: 'meeple', bad: 'red', info: 'gray' } as const
const names = (people: { display_name: string }[]) => people.map((p) => p.display_name).join(', ')

/** Why a game suits tonight, best reasons first. */
export function ReasonChips({ reasons }: { reasons: Reason[] }) {
  if (reasons.length === 0) return null
  return (
    <Group gap={4}>
      {reasons.map((r) => (
        <Badge key={r.text} size="sm" variant="light" color={TONE_COLORS[r.tone]} tt="none">
          {r.text}
        </Badge>
      ))}
    </Group>
  )
}

/** The group's combined numbers for a game, for the group's Games tab. */
export function RollupFacts({
  rollup,
  moodNames,
}: {
  rollup: GroupRollup
  moodNames: Map<string, string>
}) {
  const lines: string[] = []
  if (rollup.rating !== null) {
    const lowest =
      rollup.rated_by > 1 && rollup.lowest_rating !== null ? `, lowest ${rollup.lowest_rating}` : ''
    lines.push(`Group rating ${rollup.rating.toFixed(1)} (${rollup.rated_by} rated${lowest})`)
  }
  if (rollup.weight !== null) lines.push(`Group weight ${rollup.weight.toFixed(1)}/5`)
  if (rollup.best_at.length > 0) lines.push(`Group says best at ${rollup.best_at.join(', ')}`)
  const length = lengthLabel(rollup)
  if (length) lines.push(length)
  if (rollup.teachers.length > 0) lines.push(`Can teach: ${names(rollup.teachers)}`)
  if (rollup.want_to_play.length > 0) lines.push(`Want to play: ${names(rollup.want_to_play)}`)
  if (rollup.wishlist.length > 0) lines.push(`On wishlists: ${names(rollup.wishlist)}`)
  if (rollup.moods.length > 0) {
    lines.push(
      `Moods: ${rollup.moods
        .map((m) => `${moodNames.get(m.mood) ?? m.mood} (${names(m.people)})`)
        .join(', ')}`,
    )
  }
  if (lines.length === 0) return null
  return (
    <Text size="xs" c="dimmed">
      {lines.join(' · ')}
    </Text>
  )
}
