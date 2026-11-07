import {
  Alert,
  Anchor,
  Chip,
  Group,
  Loader,
  Modal,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { useDebouncedValue, useDisclosure } from '@mantine/hooks'
import { useNavigate, useSearchParams } from 'react-router'

import { type UserGame, type UserGameUpdate, useMyGames, useUpdateMyGame } from '../api/collection'
import { type GameSummary, useAddCustomGame, useGameSearch } from '../api/games'
import { CustomGameForm } from '../components/CustomGameForm'
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

/** For a game BGG doesn't list: one you designed, or that just isn't there. */
function AddCustomGame({ name }: { name: string }) {
  const [opened, { open, close }] = useDisclosure(false)
  const add = useAddCustomGame()
  const navigate = useNavigate()
  return (
    <>
      <Text size="sm" c="dimmed">
        Not on BoardGameGeek? Something you designed, or a game BGG just doesn't list?{' '}
        <Anchor component="button" type="button" size="sm" onClick={open}>
          Add it yourself
        </Anchor>
      </Text>
      <Modal opened={opened} onClose={close} title="Add a game that isn't on BGG">
        <Stack>
          <Text size="sm" c="dimmed">
            It goes in your games as one you own. It won't come up in anyone else's search or
            imports, but friends who see it in your games can add it to theirs.
          </Text>
          <CustomGameForm
            initial={{ name }}
            submitLabel="Add game"
            busy={add.isPending}
            error={add.error?.message}
            onCancel={close}
            onSubmit={(game) =>
              add.mutate(game, { onSuccess: (added) => navigate(`/games/${added.id}`) })
            }
          />
        </Stack>
      </Modal>
    </>
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
      <AddCustomGame name={debounced.trim()} />
    </Stack>
  )
}
