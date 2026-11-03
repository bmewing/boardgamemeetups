import {
  Alert,
  Badge,
  Button,
  Card,
  Center,
  Group,
  Image,
  Loader,
  NumberInput,
  SegmentedControl,
  Select,
  SimpleGrid,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router'

import {
  fillMyGameDetails,
  type UserGame,
  useInvalidateMyGames,
  useMyGames,
} from '../api/collection'
import { GameCard } from '../components/GameCard'
import { isOwned, isWanted, OWNERSHIP_LABELS, WISHLIST_LABELS } from '../components/userGameFields'

type Shelf = 'owned' | 'wanted' | 'all'
type Weight = 'light' | 'medium' | 'heavy'

const WEIGHT_OPTIONS = [
  { value: 'light', label: 'Light (under 2)' },
  { value: 'medium', label: 'Medium (2–3.5)' },
  { value: 'heavy', label: 'Heavy (3.5+)' },
]

interface Filters {
  shelf: Shelf
  name: string
  players: number | null
  maxMinutes: number | null
  weight: Weight | null
}

function matches(row: UserGame, f: Filters): boolean {
  const g = row.game
  if (f.shelf === 'owned' && !isOwned(row)) return false
  if (f.shelf === 'wanted' && !isWanted(row)) return false
  if (f.name && !g.name.toLowerCase().includes(f.name.trim().toLowerCase())) return false
  if (f.players !== null) {
    if (!g.min_players || !g.max_players) return false
    if (f.players < g.min_players || f.players > g.max_players) return false
  }
  if (f.maxMinutes !== null) {
    const minutes = g.max_playtime ?? g.min_playtime
    if (!minutes || minutes > f.maxMinutes) return false
  }
  if (f.weight !== null) {
    if (!g.weight) return false
    if (f.weight === 'light' && g.weight >= 2) return false
    if (f.weight === 'medium' && (g.weight < 2 || g.weight >= 3.5)) return false
    if (f.weight === 'heavy' && g.weight < 3.5) return false
  }
  return true
}

function YourAnswers({ row }: { row: UserGame }) {
  const badges = [
    row.ownership && OWNERSHIP_LABELS[row.ownership],
    row.wishlist_priority !== null && `Wishlist: ${WISHLIST_LABELS[row.wishlist_priority]}`,
    row.want_to_play && 'Want to play',
    row.rating !== null && `Rated ${row.rating}`,
    row.can_teach && 'Can teach',
  ].filter((b): b is string => Boolean(b))
  if (badges.length === 0) return null
  return (
    <Group gap={4}>
      {badges.map((b) => (
        <Badge key={b} size="sm" variant="outline">
          {b}
        </Badge>
      ))}
    </Group>
  )
}

function GameTile({ row }: { row: UserGame }) {
  return (
    <Card component={Link} to={`/games/${row.game.id}`} withBorder padding="xs">
      <Card.Section>
        <Image
          src={row.game.thumbnail_url}
          alt=""
          h={120}
          fit="contain"
          fallbackSrc="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg'/%3E"
          bg="var(--mantine-color-default-hover)"
        />
      </Card.Section>
      <Stack gap={4} mt="xs">
        <Text fw={600} size="sm" lineClamp={2}>
          {row.game.name}
        </Text>
        <YourAnswers row={row} />
      </Stack>
    </Card>
  )
}

/**
 * A BGG collection only gives each game's basics, so fetch the rest (weight, best counts)
 * a batch at a time while the page is open. Stops when BGG makes no progress.
 */
function useFillMissingDetails(enabled: boolean) {
  const invalidate = useInvalidateMyGames()
  const [remaining, setRemaining] = useState(0)
  const started = useRef(false)

  useEffect(() => {
    if (!enabled || started.current) return
    started.current = true
    let cancelled = false
    ;(async () => {
      try {
        for (;;) {
          const progress = await fillMyGameDetails()
          if (cancelled) return
          setRemaining(progress.remaining)
          if (progress.filled > 0) await invalidate()
          if (progress.remaining === 0 || progress.filled === 0) return
        }
      } catch {
        // Details are a nicety; the list works without them.
      } finally {
        if (!cancelled) setRemaining(0)
      }
    })()
    return () => {
      cancelled = true
      started.current = false
    }
  }, [enabled, invalidate])

  return remaining
}

export function CollectionPage() {
  const games = useMyGames()
  const fetchingDetails = useFillMissingDetails(Boolean(games.data?.length))
  const [view, setView] = useState<'list' | 'grid'>('list')
  const [filters, setFilters] = useState<Filters>({
    shelf: 'owned',
    name: '',
    players: null,
    maxMinutes: null,
    weight: null,
  })
  const set = <K extends keyof Filters>(key: K, value: Filters[K]) =>
    setFilters((current) => ({ ...current, [key]: value }))

  const shown = useMemo(
    () => (games.data ?? []).filter((row) => matches(row, filters)),
    [games.data, filters],
  )

  const header = (
    <Group justify="space-between">
      <Title order={2}>My games</Title>
      <Group gap="xs">
        <Button component={Link} to="/games" variant="default">
          Add a game
        </Button>
        <Button component={Link} to="/collection/pull">
          Pull from BGG
        </Button>
      </Group>
    </Group>
  )

  if (games.isPending) {
    return (
      <Stack>
        {header}
        <Center py="xl">
          <Loader />
        </Center>
      </Stack>
    )
  }
  if (games.isError) {
    return (
      <Stack>
        {header}
        <Alert color="red">{games.error.message}</Alert>
      </Stack>
    )
  }
  if (games.data.length === 0) {
    return (
      <Stack>
        {header}
        <Text c="dimmed">
          No games yet. Pull your collection from BoardGameGeek, or search for a game to add it.
        </Text>
      </Stack>
    )
  }

  return (
    <Stack>
      {header}
      <SegmentedControl
        value={filters.shelf}
        onChange={(value) => set('shelf', value as Shelf)}
        data={[
          { value: 'owned', label: 'Owned' },
          { value: 'wanted', label: 'Wishlist & want to play' },
          { value: 'all', label: 'All' },
        ]}
      />
      <SimpleGrid cols={{ base: 2, sm: 4 }}>
        <TextInput
          label="Name"
          value={filters.name}
          onChange={(e) => set('name', e.currentTarget.value)}
        />
        <NumberInput
          label="Players"
          min={1}
          max={20}
          value={filters.players ?? ''}
          onChange={(v) => set('players', typeof v === 'number' ? v : null)}
        />
        <NumberInput
          label="Max minutes"
          min={5}
          step={15}
          value={filters.maxMinutes ?? ''}
          onChange={(v) => set('maxMinutes', typeof v === 'number' ? v : null)}
        />
        <Select
          label="Weight"
          placeholder="Any"
          data={WEIGHT_OPTIONS}
          value={filters.weight}
          onChange={(v) => set('weight', v as Weight | null)}
          clearable
        />
      </SimpleGrid>
      <Group justify="space-between">
        <Text size="sm" c="dimmed">
          {shown.length} of {games.data.length} games
          {fetchingDetails > 0 && ` · fetching details from BGG for ${fetchingDetails} more`}
        </Text>
        <SegmentedControl
          size="xs"
          value={view}
          onChange={(value) => setView(value as 'list' | 'grid')}
          data={[
            { value: 'list', label: 'List' },
            { value: 'grid', label: 'Grid' },
          ]}
        />
      </Group>
      {shown.length === 0 && <Text c="dimmed">No games match these filters.</Text>}
      {view === 'list' ? (
        <Stack gap="xs">
          {shown.map((row) => (
            <GameCard key={row.game.id} game={row.game}>
              <YourAnswers row={row} />
            </GameCard>
          ))}
        </Stack>
      ) : (
        <SimpleGrid cols={{ base: 2, sm: 3, md: 4 }}>
          {shown.map((row) => (
            <GameTile key={row.game.id} row={row} />
          ))}
        </SimpleGrid>
      )}
    </Stack>
  )
}
