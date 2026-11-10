import { Loader, Select } from '@mantine/core'
import { useDebouncedValue } from '@mantine/hooks'
import { useState } from 'react'

import { type RpgSystemSummary, useRpgSystemSearch } from '../../api/rpg'

/**
 * Type a name, pick a system: searches ours first, then RPGGeek (which can take a few
 * seconds). `value` shows the current pick; picking again replaces it.
 */
export function RpgSystemSearchSelect({
  value,
  onPick,
  label,
  ariaLabel,
  required,
  clearable,
}: {
  value: RpgSystemSummary | null
  onPick: (system: RpgSystemSummary | null) => void
  label?: string
  ariaLabel?: string
  required?: boolean
  clearable?: boolean
}) {
  const [search, setSearch] = useState('')
  const [debounced] = useDebouncedValue(search, 300)
  const results = useRpgSystemSearch(debounced)
  const found = results.data ?? []
  // Keep the current pick in the options so its name shows.
  const systems = value && !found.some((s) => s.id === value.id) ? [value, ...found] : found

  return (
    <Select
      label={label}
      aria-label={ariaLabel}
      required={required}
      clearable={clearable}
      placeholder="Search RPG systems…"
      searchable
      searchValue={search}
      onSearchChange={setSearch}
      value={value ? String(value.id) : null}
      // The API already filtered; don't filter its results again by label.
      filter={({ options }) => options}
      data={systems.map((s) => ({ value: String(s.id), label: s.name }))}
      nothingFoundMessage={
        debounced.trim().length >= 2 && !results.isFetching ? 'No systems found' : null
      }
      rightSection={results.isFetching ? <Loader size="xs" /> : null}
      onChange={(id) => {
        onPick(systems.find((s) => String(s.id) === id) ?? null)
        setSearch('')
      }}
    />
  )
}
