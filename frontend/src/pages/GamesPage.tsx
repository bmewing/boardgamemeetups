import { Alert, Loader, Stack, Text, TextInput, Title } from '@mantine/core'
import { useDebouncedValue } from '@mantine/hooks'
import { useSearchParams } from 'react-router'

import { useGameSearch } from '../api/games'
import { GameCard } from '../components/GameCard'

export function GamesPage() {
  // Keep the query in the URL so back-navigation from a game returns to the same results.
  const [params, setParams] = useSearchParams()
  const query = params.get('q') ?? ''
  const [debounced] = useDebouncedValue(query, 300)
  const search = useGameSearch(debounced)

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
          <GameCard key={game.id} game={game} />
        ))}
      </Stack>
    </Stack>
  )
}
