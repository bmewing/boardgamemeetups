import { Loader, Select } from '@mantine/core'
import { useDebouncedValue } from '@mantine/hooks'
import { useState } from 'react'

import type { GameBrief } from '../api/fileImport'
import { useGameSearch } from '../api/games'

function label(game: { name: string; year_published: number | null }) {
  return game.year_published ? `${game.name} (${game.year_published})` : game.name
}

/** Type a name, pick a game: searches our catalog first, then BGG. */
export function GameSearchSelect({
  onPick,
  ariaLabel,
}: {
  onPick: (game: GameBrief) => void
  ariaLabel: string
}) {
  const [search, setSearch] = useState('')
  const [debounced] = useDebouncedValue(search, 300)
  const results = useGameSearch(debounced)
  const games = results.data ?? []

  return (
    <Select
      aria-label={ariaLabel}
      placeholder="Search BGG…"
      searchable
      searchValue={search}
      onSearchChange={setSearch}
      value={null}
      // The API already filtered; don't filter its results again by label.
      filter={({ options }) => options}
      data={games.map((g) => ({ value: String(g.id), label: label(g) }))}
      nothingFoundMessage={
        debounced.trim().length >= 2 && !results.isFetching ? 'No games found' : null
      }
      rightSection={results.isFetching ? <Loader size="xs" /> : null}
      onChange={(value) => {
        const game = games.find((g) => String(g.id) === value)
        if (!game) return
        onPick({
          id: game.id,
          name: game.name,
          year_published: game.year_published,
          thumbnail_url: game.thumbnail_url,
          is_expansion: game.is_expansion,
        })
        setSearch('')
      }}
      size="xs"
      w={{ base: '100%', sm: 260 }}
    />
  )
}
