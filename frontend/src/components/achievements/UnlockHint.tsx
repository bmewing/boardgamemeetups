import { Group, Text } from '@mantine/core'

import { useMe } from '../../api/me'
import type { AchievementName } from '../pieces/shapes'
import { Reward } from './Reward'
import { rewardName, rewardOf, standingsOf } from './rewards'

/**
 * A one-line nudge beside the thing that earns an achievement, for someone who hasn't
 * earned it yet: "Unlock the battleship: …". Nothing once it's earned, or for a badge.
 */
export function UnlockHint({ achievement, text }: { achievement: AchievementName; text: string }) {
  const me = useMe()
  if (!me.data) return null
  const standing = standingsOf(me.data).get(achievement)
  if (!standing || standing.earned_at) return null
  const reward = rewardOf(me.data, achievement)
  const gives = rewardName(reward)
  if (!gives) return null
  return (
    <Group gap="xs" wrap="nowrap">
      <Reward reward={reward} holder={me.data} earned={false} size={24} />
      <Text size="sm" c="dimmed">
        Unlock {gives}: {text}
      </Text>
    </Group>
  )
}
