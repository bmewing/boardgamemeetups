import { Button, CloseButton, Loader, Paper, Stack, Text, TextInput } from '@mantine/core'
import { useDebouncedValue } from '@mantine/hooks'
import { type Ref, useState } from 'react'

import { useMyGames } from '../api/collection'
import { useGameSearch } from '../api/games'
import { AddCustomGame } from './AddCustomGame'
import { GameCard } from './GameCard'
import { ErrorNote } from './mascot/MascotNote'
import { QuickAnswers } from './QuickAnswers'

// Enough to find the game you meant without pushing your own games off the screen.
const SHOWN_AT_FIRST = 5

function SearchGlyph() {
  return (
    <svg width={18} height={18} viewBox="0 0 24 24" fill="none" aria-hidden>
      <circle cx="11" cy="11" r="7" stroke="currentColor" strokeWidth="2" />
      <path d="m20 20-3.5-3.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  )
}

/**
 * Search BGG from your games page and add what you find without leaving it: each result
 * has one-tap "own it / wishlist / want to play" answers, and lands in your list at once.
 */
export function AddGameSearch({
  query,
  onQueryChange,
  inputRef,
}: {
  query: string
  onQueryChange: (query: string) => void
  inputRef?: Ref<HTMLInputElement>
}) {
  const [showAll, setShowAll] = useState(false)
  const [debounced] = useDebouncedValue(query, 300)
  const search = useGameSearch(debounced)
  const myGames = useMyGames()
  const mine = new Map((myGames.data ?? []).map((r) => [r.game.id, r]))

  // Checking `query` too means clearing the box hides results at once, not after the debounce.
  const searching = query.trim().length >= 2 && debounced.trim().length >= 2
  const results = searching ? (search.data ?? []) : []
  const shown = showAll ? results : results.slice(0, SHOWN_AT_FIRST)
  const change = (next: string) => {
    onQueryChange(next)
    setShowAll(false)
  }

  return (
    <Paper withBorder radius="md" p="md" bg="var(--mantine-primary-color-light)">
      <Stack gap="sm">
        <TextInput
          ref={inputRef}
          label="Add a game"
          description="Search BoardGameGeek, then tap whether you own it, want it, or want to play it."
          placeholder="e.g. Wingspan"
          size="md"
          leftSection={<SearchGlyph />}
          value={query}
          onChange={(event) => change(event.currentTarget.value)}
          onKeyDown={(event) => {
            if (event.key === 'Escape') change('')
          }}
          rightSection={
            search.isFetching && searching ? (
              <Loader size="xs" />
            ) : query ? (
              <CloseButton aria-label="Clear search" onClick={() => change('')} />
            ) : null
          }
        />
        {searching && search.isError && <ErrorNote error={search.error} onRetry={search.refetch} />}
        {searching && search.isSuccess && results.length === 0 && !search.isFetching && (
          <Text size="sm" c="dimmed">
            No games found for “{debounced.trim()}”.
          </Text>
        )}
        {shown.length > 0 && (
          <Stack gap="xs">
            {shown.map((game) => (
              <GameCard
                key={game.id}
                game={game}
                below={<QuickAnswers game={game} row={mine.get(game.id)} />}
              />
            ))}
          </Stack>
        )}
        {results.length > shown.length && (
          <Button variant="subtle" size="xs" w="fit-content" onClick={() => setShowAll(true)}>
            Show all {results.length} results
          </Button>
        )}
        {searching && !search.isPending && <AddCustomGame name={debounced.trim()} />}
      </Stack>
    </Paper>
  )
}
