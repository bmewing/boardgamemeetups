import { Loader, Select } from '@mantine/core'
import { useDebouncedValue } from '@mantine/hooks'
import { useState } from 'react'

import { useBgaSearch } from '../api/bga'

/** Type a name, pick a game on Board Game Arena; hands back the catalog game's id. */
export function BgaSearchSelect({
  onPick,
  ariaLabel,
}: {
  onPick: (gameId: number) => void
  ariaLabel: string
}) {
  const [search, setSearch] = useState('')
  const [debounced] = useDebouncedValue(search, 300)
  const results = useBgaSearch(debounced)
  const games = results.data ?? []

  return (
    <Select
      aria-label={ariaLabel}
      placeholder="Nominate any game on Board Game Arena…"
      searchable
      searchValue={search}
      onSearchChange={setSearch}
      value={null}
      // The API already filtered; don't filter its results again by label.
      filter={({ options }) => options}
      data={games.map((g) => ({
        value: String(g.game.id),
        label: g.premium ? `${g.name} (Premium)` : g.name,
      }))}
      nothingFoundMessage={
        debounced.trim().length >= 2 && !results.isFetching ? 'Not on BGA' : null
      }
      rightSection={results.isFetching ? <Loader size="xs" /> : null}
      onChange={(value) => {
        if (!value) return
        onPick(Number(value))
        setSearch('')
      }}
    />
  )
}
