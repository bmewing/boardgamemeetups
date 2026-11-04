import { Alert, Chip, Group, Loader, Stack, Text, TextInput, Title } from '@mantine/core'
import { useDebouncedValue } from '@mantine/hooks'
import { useSearchParams } from 'react-router'

import { type UserGame, type UserGameUpdate, useMyGames, useUpdateMyGame } from '../api/collection'
import { type GameSummary, useGameSearch } from '../api/games'
import { GameCard } from '../components/GameCard'
import { isOwned } from '../components/userGameFields'

// BGG's "Like to have", the middle of its five wishlist priorities.
const DEFAULT_WISHLIST_PRIORITY = 3

/** One-tap answers for a search result; the rest are on the game's page. */
function QuickAnswers({ game, row }: { game: GameSummary; row: UserGame | undefined }) {
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

export function GamesPage() {
  // Keep the query in the URL so back-navigation from a game returns to the same results.
  const [params, setParams] = useSearchParams()
  const query = params.get('q') ?? ''
  const [debounced] = useDebouncedValue(query, 300)
  const search = useGameSearch(debounced)
  const myGames = useMyGames()
  const mine = new Map((myGames.data ?? []).map((r) => [r.game.id, r]))

  return (
    <Stack>
      <Title order={2}>Games</Title>
      <TextInput
        label="Search BoardGameGeek"
        placeholder="e.g. Wingspan"
        value={query}
        onChange={(event) =>
          setParams(event.currentTarget.value ? { q: event.currentTarget.value } : {}, {
            replace: true,
          })
        }
        rightSection={search.isFetching ? <Loader size="xs" /> : null}
        autoFocus
      />
      {search.isError && <Alert color="red">{search.error.message}</Alert>}
      {search.data?.length === 0 && !search.isFetching && (
        <Text c="dimmed">No games found for “{debounced.trim()}”.</Text>
      )}
      <Stack gap="xs">
        {search.data?.map((game) => (
          <GameCard
            key={game.id}
            game={game}
            below={<QuickAnswers game={game} row={mine.get(game.id)} />}
          />
        ))}
      </Stack>
    </Stack>
  )
}
