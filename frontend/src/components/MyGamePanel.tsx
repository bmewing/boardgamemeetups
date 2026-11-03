import { Alert, Card, Group, Select, Stack, Switch, Text, Title } from '@mantine/core'

import { type Ownership, type UserGameUpdate, useMyGames, useUpdateMyGame } from '../api/collection'
import { RemoveGameButton } from './RemoveGameButton'
import { expansionsInList, OWNERSHIP_LABELS } from './userGameFields'

const NOT_OWNED = 'none'
const OWNERSHIP_OPTIONS = [
  { value: NOT_OWNED, label: "Don't own it" },
  ...Object.entries(OWNERSHIP_LABELS).map(([value, label]) => ({ value, label })),
]
// BGG's "Like to have", the middle of its five wishlist priorities.
const DEFAULT_WISHLIST_PRIORITY = 3

/** Add a game to your list, say whether you own or want it, or remove it. */
export function MyGamePanel({ gameId }: { gameId: number }) {
  const games = useMyGames()
  const update = useUpdateMyGame()
  const row = games.data?.find((r) => r.game.id === gameId)
  const save = (changes: UserGameUpdate) => update.mutate({ gameId, changes })
  const busy = games.isPending || update.isPending

  return (
    <Card withBorder>
      <Stack gap="sm">
        <Group justify="space-between">
          <Title order={4}>My games</Title>
          {row && (
            <RemoveGameButton
              game={row.game}
              expansions={expansionsInList(row.game, games.data ?? [])}
              variant="text"
            />
          )}
        </Group>
        {!row && !games.isPending && (
          <Text size="sm" c="dimmed">
            Not in your games yet. Say whether you own or want it to add it.
          </Text>
        )}
        <Group align="flex-end">
          <Select
            label="Ownership"
            data={OWNERSHIP_OPTIONS}
            value={row?.ownership ?? NOT_OWNED}
            allowDeselect={false}
            disabled={busy}
            onChange={(value) =>
              save({ ownership: value === NOT_OWNED ? null : (value as Ownership) })
            }
            w={200}
          />
          <Switch
            label="On my wishlist"
            checked={row?.wishlist_priority != null}
            disabled={busy}
            onChange={(e) =>
              save({
                wishlist_priority: e.currentTarget.checked ? DEFAULT_WISHLIST_PRIORITY : null,
              })
            }
          />
          <Switch
            label="Want to play"
            checked={row?.want_to_play ?? false}
            disabled={busy}
            onChange={(e) => save({ want_to_play: e.currentTarget.checked })}
          />
        </Group>
        {update.isError && <Alert color="red">{update.error.message}</Alert>}
      </Stack>
    </Card>
  )
}
