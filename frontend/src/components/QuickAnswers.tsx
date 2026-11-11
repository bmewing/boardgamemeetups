import { Chip, Group, Stack, Text } from '@mantine/core'

import { type UserGame, type UserGameUpdate, useUpdateMyGame } from '../api/collection'
import type { GameSummary } from '../api/games'
import { isOwned } from './userGameFields'

// BGG's "Like to have", the middle of its five wishlist priorities.
const DEFAULT_WISHLIST_PRIORITY = 3

/** One-tap answers for a search result; the rest are on the game's page. */
export function QuickAnswers({ game, row }: { game: GameSummary; row: UserGame | undefined }) {
  const update = useUpdateMyGame()
  const save = (changes: UserGameUpdate) => update.mutate({ gameId: game.id, changes, game })
  return (
    <Stack gap={4}>
      <Group gap="xs">
        <Chip
          size="xs"
          checked={row ? isOwned(row) : false}
          onChange={(on) => save({ ownership: on ? 'owned' : null })}
        >
          I own it
        </Chip>
        <Chip
          size="xs"
          checked={row?.wishlist_priority != null}
          onChange={(on) => save({ wishlist_priority: on ? DEFAULT_WISHLIST_PRIORITY : null })}
        >
          On my wishlist
        </Chip>
        <Chip
          size="xs"
          checked={row?.want_to_play ?? false}
          onChange={(on) => save({ want_to_play: on })}
        >
          Want to play
        </Chip>
      </Group>
      {update.isError && (
        <Text size="xs" c="red">
          {update.error.message}
        </Text>
      )}
    </Stack>
  )
}
