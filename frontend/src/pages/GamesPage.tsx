import { Loader, Stack, Text, TextInput, Title } from '@mantine/core'
import { useDebouncedValue } from '@mantine/hooks'
import { useSearchParams } from 'react-router'

import { useMyGames } from '../api/collection'
import { useGameSearch } from '../api/games'
import { AddCustomGame } from '../components/AddCustomGame'
import { GameCard } from '../components/GameCard'
import { ErrorNote, MascotNote } from '../components/mascot/MascotNote'
import { QuickAnswers } from '../components/QuickAnswers'

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
      {search.isError && <ErrorNote error={search.error} onRetry={search.refetch} />}
      {!query.trim() && (
        <MascotNote pose="twirl" title="What's your next game?">
          <Text c="dimmed" maw={420}>
            Search for a game to mark it as yours, wishlist it, or say you want to play it.
          </Text>
        </MascotNote>
      )}
      {search.data?.length === 0 && !search.isFetching && (
        <MascotNote pose="think">
          <Text c="dimmed">No games found for “{debounced.trim()}”.</Text>
        </MascotNote>
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
      <AddCustomGame name={debounced.trim()} />
    </Stack>
  )
}
