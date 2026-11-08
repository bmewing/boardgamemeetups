import { Button, Group, Text } from '@mantine/core'
import { useState } from 'react'
import { Link } from 'react-router'

import type { UserProfile } from '../../api/client'
import { ACHIEVEMENTS, type AchievementName } from '../pieces/shapes'
import { Reward } from './Reward'
import { nextAchievement, rewardName, rewardOf } from './rewards'

const SKIPPED_KEY = 'skippedAchievements'

function readSkipped(): AchievementName[] {
  try {
    const stored = window.localStorage.getItem(SKIPPED_KEY)
    return stored ? (JSON.parse(stored) as AchievementName[]) : []
  } catch {
    return []
  }
}

function saveSkipped(skipped: AchievementName[]) {
  try {
    window.localStorage.setItem(SKIPPED_KEY, JSON.stringify(skipped))
  } catch {
    // Without storage, "not now" only lasts until the page reloads.
  }
}

/**
 * The next thing to try on the site, as an achievement with what it unlocks and a button
 * that goes there. "Not now" moves on to the one after. Renders nothing once the path is done.
 */
export function NextAchievement({
  profile,
  ruledOut = [],
  wrap,
}: {
  profile: UserProfile
  /** Ones that make no sense right now, like joining a group with no invite waiting. */
  ruledOut?: AchievementName[]
  /** Frames the card, given its title; the card is left out entirely when there's nothing. */
  wrap: (title: string, card: React.ReactNode) => React.ReactNode
}) {
  const [skipped, setSkipped] = useState(readSkipped)
  const next = nextAchievement(profile, [...ruledOut, ...skipped])
  if (!next) return null
  const { title, how, to, action } = ACHIEVEMENTS[next]
  const reward = rewardOf(profile, next)
  const gives = rewardName(reward)

  const skip = () => {
    const more = [...skipped, next]
    setSkipped(more)
    saveSkipped(more)
  }

  return wrap(
    'Next achievement',
    <Group wrap="nowrap" align="flex-start" gap="sm">
      <Reward reward={reward} holder={profile} earned={false} size={48} />
      <div style={{ minWidth: 0 }}>
        <Text fw={700}>{title}</Text>
        <Text size="sm">
          {how}
          {gives ? ` to unlock ${gives}.` : '.'}
        </Text>
        <Group gap="xs" mt="xs">
          <Button component={Link} to={to} size="xs">
            {action}
          </Button>
          <Button size="xs" variant="subtle" color="gray" onClick={skip}>
            Not now
          </Button>
        </Group>
      </div>
    </Group>,
  )
}
