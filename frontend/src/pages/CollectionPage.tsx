import {
  Badge,
  Box,
  Button,
  Card,
  Group,
  Image,
  NumberInput,
  SegmentedControl,
  Select,
  SimpleGrid,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { type ReactNode, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router'

import {
  fillMyGameDetails,
  type UserGame,
  useInvalidateMyGames,
  useMyGames,
} from '../api/collection'
import { GameCard } from '../components/GameCard'
import { playerRange, widenedLabel } from '../components/gameFacts'
import { GameAnswersEditor } from '../components/GameAnswersEditor'
import { ErrorNote, LoadingNote, MascotNote } from '../components/mascot/MascotNote'
import { FindMissingBaseGames } from '../components/MissingBaseGames'
import { RemoveGameButton } from '../components/RemoveGameButton'
import {
  expansionsInList,
  isOwned,
  isWanted,
  OWNERSHIP_LABELS,
  teaches,
  WISHLIST_LABELS,
} from '../components/userGameFields'

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

type Game = UserGame['game']

/** The expansions you own, by the base games they fit. */
function expansionsByBase(rows: UserGame[]): Map<number, Game[]> {
  const byBase = new Map<number, Game[]>()
  for (const row of rows) {
    if (!row.game.is_expansion || !isOwned(row)) continue
    for (const base of row.game.base_game_ids) {
      byBase.set(base, [...(byBase.get(base) ?? []), row.game])
    }
  }
  return byBase
}

function matches(row: UserGame, f: Filters, expansions: Game[]): boolean {
  const g = row.game
  if (f.shelf === 'owned' && !isOwned(row)) return false
  if (f.shelf === 'wanted' && !isWanted(row)) return false
  if (f.name && !g.name.toLowerCase().includes(f.name.trim().toLowerCase())) return false
  if (f.players !== null) {
    // Your expansions for a game can let it seat more (or fewer).
    const { min_players: min, max_players: max } = playerRange(g, expansions)
    if (!min || !max) return false
    if (f.players < min || f.players > max) return false
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

/** Badges for your answers; `statusOnly` leaves out the ones the list row lets you edit. */
function YourAnswers({ row, statusOnly = false }: { row: UserGame; statusOnly?: boolean }) {
  const badges = [
    row.ownership && OWNERSHIP_LABELS[row.ownership],
    row.wishlist_priority !== null && `Wishlist: ${WISHLIST_LABELS[row.wishlist_priority]}`,
    ...(statusOnly
      ? []
      : [
          row.want_to_play && 'Want to play',
          row.rating !== null && `Rated ${row.rating}`,
          teaches(row) && 'Can teach',
        ]),
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

/** The expansions you own for a game, and the player range they give it. */
function YourExpansions({ game, expansions }: { game: Game; expansions: Game[] }) {
  if (expansions.length === 0) return null
  const widened = widenedLabel(game, playerRange(game, expansions))
  return (
    <Text size="xs" c="dimmed">
      With your {expansions.map((e) => e.name).join(', ')}
      {widened && ` (${widened})`}
    </Text>
  )
}

/** The remove button sits beside the card's link, not inside it, so clicks don't navigate. */
function WithRemove({
  row,
  allRows,
  children,
  overImage = false,
}: {
  row: UserGame
  allRows: UserGame[]
  children: ReactNode
  overImage?: boolean
}) {
  return (
    <Box pos="relative">
      {children}
      <Box pos="absolute" top={8} right={8}>
        <RemoveGameButton
          game={row.game}
          expansions={expansionsInList(row.game, allRows)}
          overImage={overImage}
        />
      </Box>
    </Box>
  )
}

function GameTile({ row }: { row: UserGame }) {
  return (
    <Card component={Link} to={`/games/${row.game.id}`} withBorder padding="xs" h="100%">
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

  const expansions = useMemo(() => expansionsByBase(games.data ?? []), [games.data])
  const shown = useMemo(
    () =>
      (games.data ?? []).filter((row) => matches(row, filters, expansions.get(row.game.id) ?? [])),
    [games.data, filters, expansions],
  )

  const header = (
    <Group justify="space-between">
      <Title order={2}>My games</Title>
      <Group gap="xs">
        <Button component={Link} to="/games" variant="default">
          Add a game
        </Button>
        <FindMissingBaseGames />
        <Button component={Link} to="/collection/import" variant="default">
          Import a file
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
        <LoadingNote>Pulling your games off the shelf…</LoadingNote>
      </Stack>
    )
  }
  if (games.isError) {
    return (
      <Stack>
        {header}
        <ErrorNote error={games.error} onRetry={games.refetch} />
      </Stack>
    )
  }
  if (games.data.length === 0) {
    return (
      <Stack>
        {header}
        <MascotNote pose="twirl" size={160} title="Your shelf is empty">
          <Text c="dimmed" maw={460}>
            No games yet. Pull your collection from BoardGameGeek, import a spreadsheet, or search
            for a game to add it.
          </Text>
        </MascotNote>
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
      {shown.length === 0 && (
        <MascotNote pose="think" size={112}>
          <Text c="dimmed">No games match these filters.</Text>
        </MascotNote>
      )}
      {view === 'list' ? (
        <Stack gap="xs">
          {shown.map((row) => (
            <WithRemove key={row.game.id} row={row} allRows={games.data}>
              <GameCard game={row.game} pr={44} below={<GameAnswersEditor row={row} />}>
                <YourAnswers row={row} statusOnly />
                <YourExpansions game={row.game} expansions={expansions.get(row.game.id) ?? []} />
              </GameCard>
            </WithRemove>
          ))}
        </Stack>
      ) : (
        <SimpleGrid cols={{ base: 2, sm: 3, md: 4 }}>
          {shown.map((row) => (
            <WithRemove key={row.game.id} row={row} allRows={games.data} overImage>
              <GameTile row={row} />
            </WithRemove>
          ))}
        </SimpleGrid>
      )}
    </Stack>
  )
}
