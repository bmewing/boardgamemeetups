import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ME_KEY } from '../../api/me'
import { createQueryClient } from '../../api/queryClient'
import { earnedProfile, profile } from '../../test/fixtures'
import { mockApi, signIn } from '../../test/mocks'
import { renderWithProviders } from '../../test/render'
import { NextAchievement } from './NextAchievement'
import { nextAchievement } from './rewards'
import { UnlockCelebration } from './UnlockCelebration'

const withEarned = (...earned: Parameters<typeof earnedProfile>) => ({
  ...profile,
  ...earnedProfile(...earned),
})

const frame = (title: string, card: ReactNode) => (
  <section aria-label={title}>
    <h2>{title}</h2>
    {card}
  </section>
)

describe('nextAchievement', () => {
  it('walks the suggested path, skipping what is done or ruled out', () => {
    expect(nextAchievement(withEarned())).toBe('add_game')
    expect(nextAchievement(withEarned(['add_game']))).toBe('make_friend')
    expect(nextAchievement(withEarned(['add_game', 'make_friend']), ['join_group'])).toBe(
      'start_group',
    )
  })
})

describe('NextAchievement', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  it('says what to do, what it unlocks, and moves on when skipped', async () => {
    renderWithProviders(<NextAchievement profile={withEarned(['add_game'])} wrap={frame} />)

    expect(screen.getByText('Player two')).toBeInTheDocument()
    expect(screen.getByText('Make a friend to unlock the scottie dog.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Find friends' })).toHaveAttribute('href', '/friends')

    await userEvent.click(screen.getByRole('button', { name: 'Not now' }))

    expect(screen.getByText('Pulled up a chair')).toBeInTheDocument()
  })

  it('shows nothing once the path is done', () => {
    const done = withEarned([
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
    ])
    renderWithProviders(<NextAchievement profile={done} wrap={frame} />)

    expect(screen.queryByRole('region', { name: 'Next achievement' })).not.toBeInTheDocument()
  })
})

describe('UnlockCelebration', () => {
  beforeEach(() => {
    signIn()
  })

  it('celebrates new unlocks, tries the new piece on, and marks them seen', async () => {
    const sent: unknown[] = []
    let seen = false
    const earned = withEarned(['start_group', 'stay_in_loop', 'vote'], ['start_group', 'vote'])
    mockApi({
      'PATCH /api/me': async (request) => {
        sent.push(await request.json())
        return Response.json(earned)
      },
      'POST /api/me/achievements/seen': () => {
        seen = true
        return Response.json(withEarned(['start_group', 'stay_in_loop', 'vote']))
      },
    })
    renderWithProviders(<UnlockCelebration profile={earned} />)

    expect(await screen.findByText('2 achievements unlocked!')).toBeInTheDocument()
    expect(screen.getByText('Start a group. You unlocked the rook!')).toBeInTheDocument()
    expect(screen.getByText('Vote for a game someone else put forward.')).toBeInTheDocument()
    expect(screen.queryByText('In the loop')).not.toBeInTheDocument() // not new

    await userEvent.click(screen.getByRole('button', { name: 'Try it on' }))

    await waitFor(() => expect(seen).toBe(true))
    expect(sent).toEqual([{ piece: 'rook' }])
    await waitFor(() =>
      expect(screen.queryByText('2 achievements unlocked!')).not.toBeInTheDocument(),
    )
  })

  it('shows nothing when nothing is new', () => {
    renderWithProviders(<UnlockCelebration profile={withEarned(['start_group'])} />)

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})

describe('createQueryClient', () => {
  it('refreshes the profile after any change but its own', async () => {
    const client = createQueryClient()
    const invalidate = vi.spyOn(client, 'invalidateQueries')
    const run = (options: object) =>
      client
        .getMutationCache()
        .build(client, { mutationFn: async () => 1, ...options })
        .execute(undefined)

    await run({})
    await run({ mutationKey: ME_KEY })

    expect(invalidate).toHaveBeenCalledTimes(1)
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ME_KEY })
  })
})
