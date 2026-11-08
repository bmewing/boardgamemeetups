import { Anchor, Group, Progress, Stack, Text, Title, VisuallyHidden } from '@mantine/core'
import { Link } from 'react-router'

import type { UserProfile } from '../../api/client'
import { ACHIEVEMENTS, CHAPTERS, type ChapterName } from '../pieces/shapes'
import classes from './achievements.module.css'
import { Reward } from './Reward'
import { inChapter, isEarned, rewardName, rewardOf, type Standing } from './rewards'

const EARNED_ON = new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric' })

/** Every achievement, chapter by chapter, with what each one unlocks. */
export function AchievementList({ profile }: { profile: UserProfile }) {
  const total = profile.achievements.length
  const earned = profile.achievements.filter(isEarned).length

  return (
    <Stack gap="sm">
      <Title order={4}>Achievements</Title>
      <div>
        <Text size="sm" c="dimmed" mb={4}>
          {earned} of {total} earned. Most unlock a piece or a color.
        </Text>
        <Progress
          value={(earned / total) * 100}
          aria-label={`${earned} of ${total} achievements earned`}
        />
      </div>
      <div className={classes.chapters}>
        {(Object.keys(CHAPTERS) as ChapterName[]).map((chapter) => (
          <Chapter key={chapter} chapter={chapter} profile={profile} />
        ))}
      </div>
    </Stack>
  )
}

function Chapter({ chapter, profile }: { chapter: ChapterName; profile: UserProfile }) {
  const items = inChapter(profile, chapter)
  const done = items.filter(isEarned).length
  const { label, blurb } = CHAPTERS[chapter]
  return (
    <section aria-label={label}>
      <Group justify="space-between" align="baseline" mb={6}>
        <div>
          <Text fw={700}>{label}</Text>
          <Text size="xs" c="dimmed">
            {blurb}
          </Text>
        </div>
        <Text size="sm" c="dimmed">
          {done} / {items.length}
        </Text>
      </Group>
      <ul className={classes.list}>
        {items.map((standing) => (
          <Item key={standing.achievement} standing={standing} profile={profile} />
        ))}
      </ul>
    </section>
  )
}

function Item({ standing, profile }: { standing: Standing; profile: UserProfile }) {
  const { title, how, to, action } = ACHIEVEMENTS[standing.achievement]
  const earned = isEarned(standing)
  const reward = rewardOf(profile, standing.achievement)
  const gives = rewardName(reward)
  const counted = standing.goal !== null && standing.goal > 1 && !earned
  return (
    <li className={classes.item} data-earned={earned || undefined}>
      <Reward reward={reward} holder={profile} earned={earned} />
      <div className={classes.itemText}>
        <Text size="sm" fw={700}>
          {title}
          {earned && (
            <>
              <span aria-hidden> ✓</span>
              <VisuallyHidden> (earned)</VisuallyHidden>
            </>
          )}
        </Text>
        <Text size="xs" c="dimmed">
          {how}
          {gives && ` · unlocks ${gives}`}
        </Text>
        {counted && (
          <Text size="xs" c="dimmed">
            {standing.progress} / {standing.goal} so far
          </Text>
        )}
        {earned && standing.earned_at ? (
          <Text size="xs" c="dimmed">
            Earned {EARNED_ON.format(new Date(standing.earned_at))}
          </Text>
        ) : (
          <Anchor component={Link} to={to} size="xs">
            {action} →
          </Anchor>
        )}
      </div>
    </li>
  )
}
