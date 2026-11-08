import { Button, Group, Modal, Stack, Text } from '@mantine/core'
import { useState } from 'react'
import { useNavigate } from 'react-router'

import type { UserProfile } from '../../api/client'
import { useSeeAchievements, useUpdateMe } from '../../api/me'
import { Grouper } from '../mascot/Grouper'
import { ACHIEVEMENTS } from '../pieces/shapes'
import classes from './achievements.module.css'
import { Reward } from './Reward'
import { rewardName, rewardOf, type Standing } from './rewards'

/**
 * Pops up when something new has been earned, says what it unlocked, and offers to try on
 * a new piece. Closing it marks everything seen. Shows what was new when it opened, even if
 * another page marks it seen meanwhile.
 */
export function UnlockCelebration({ profile }: { profile: UserProfile }) {
  const [shown, setShown] = useState<Standing[]>([])
  // Closed ones stay closed while the server catches up on them being seen.
  const [closed, setClosed] = useState<ReadonlySet<string>>(new Set())
  const fresh = profile.achievements.filter(
    (a) => a.new && !closed.has(a.achievement),
  ) as Standing[]
  const see = useSeeAchievements()
  const update = useUpdateMe()
  const navigate = useNavigate()

  // Open as soon as there's something new and nothing already showing.
  if (fresh.length > 0 && shown.length === 0) setShown(fresh)
  if (shown.length === 0) return null

  const close = () => {
    setClosed(new Set([...closed, ...shown.map((s) => s.achievement)]))
    setShown([])
    see.mutate()
  }
  const rewards = shown.map((s) => ({ standing: s, reward: rewardOf(profile, s.achievement) }))
  const newPiece = rewards.find((r) => r.reward.kind === 'piece')?.reward
  const newColor = rewards.find((r) => r.reward.kind === 'color')?.reward
  const tryOn = () => {
    update.mutate({
      ...(newPiece?.kind === 'piece' ? { piece: newPiece.piece } : {}),
      ...(newColor?.kind === 'color' ? { piece_color: newColor.color } : {}),
    })
    close()
  }

  return (
    <Modal
      opened
      onClose={close}
      centered
      title={
        shown.length === 1 ? 'Achievement unlocked!' : `${shown.length} achievements unlocked!`
      }
    >
      <Stack align="center" gap="sm">
        <Grouper pose="cheer" size={120} label="" />
        <ul className={classes.celebrateList}>
          {rewards.map(({ standing, reward }) => {
            const { title, how } = ACHIEVEMENTS[standing.achievement]
            const gives = rewardName(reward)
            return (
              <li key={standing.achievement}>
                <Group wrap="nowrap" gap="sm">
                  <Reward reward={reward} holder={profile} earned size={40} />
                  <div>
                    <Text fw={700}>{title}</Text>
                    <Text size="sm" c="dimmed">
                      {how}
                      {gives ? `. You unlocked ${gives}!` : '.'}
                    </Text>
                  </div>
                </Group>
              </li>
            )
          })}
        </ul>
        <Group>
          {(newPiece || newColor) && <Button onClick={tryOn}>Try it on</Button>}
          <Button
            variant="default"
            onClick={() => {
              close()
              navigate('/profile')
            }}
          >
            See all achievements
          </Button>
        </Group>
      </Stack>
    </Modal>
  )
}
