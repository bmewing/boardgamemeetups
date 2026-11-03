import {
  Alert,
  Badge,
  Button,
  Card,
  Center,
  Group,
  Loader,
  Modal,
  Stack,
  Text,
} from '@mantine/core'
import { useMutation } from '@tanstack/react-query'
import { useState } from 'react'

import {
  type BaseGameChoice,
  type BaseGameSuggestion,
  findMissingBaseGames,
  useRemoveMyGame,
  useUpdateMyGame,
} from '../api/collection'
import type { GameSummary } from '../api/games'
import { GameCard } from './GameCard'
import { GameSearchSelect } from './GameSearchSelect'
import { OWNERSHIP_LABELS, plural } from './userGameFields'

// BGG's "Like to have", the middle of its five wishlist priorities.
const WISHLIST_PRIORITY = 3

function names(games: { name: string }[]) {
  return games.map((g) => g.name).join(', ')
}

function SuggestionCard({
  suggestion,
  onDone,
}: {
  suggestion: BaseGameSuggestion
  onDone: () => void
}) {
  const update = useUpdateMyGame()
  const remove = useRemoveMyGame()
  const { game } = suggestion
  const busy = update.isPending || remove.isPending
  const save = (changes: Parameters<typeof update.mutate>[0]['changes']) =>
    update.mutate({ gameId: game.id, changes }, { onSuccess: onDone })

  return (
    <Stack gap={6}>
      <GameCard game={game}>
        <Text size="sm">
          For your {suggestion.expansions.length === 1 ? 'expansion' : 'expansions'}:{' '}
          {names(suggestion.expansions)}
        </Text>
        <Group gap={4}>
          {suggestion.on_wishlist && (
            <Badge size="sm" variant="outline">
              On your wishlist
            </Badge>
          )}
          {suggestion.ownership && (
            <Badge size="sm" variant="outline">
              {OWNERSHIP_LABELS[suggestion.ownership]}
            </Badge>
          )}
        </Group>
      </GameCard>
      <Group gap="xs">
        <Button size="xs" disabled={busy} onClick={() => save({ ownership: 'owned' })}>
          I own it
        </Button>
        {!suggestion.on_wishlist && (
          <Button
            size="xs"
            variant="default"
            disabled={busy}
            onClick={() => save({ wishlist_priority: WISHLIST_PRIORITY })}
          >
            Add to wishlist
          </Button>
        )}
        <Button
          size="xs"
          variant="subtle"
          color="gray"
          disabled={busy}
          onClick={() => remove.mutate({ gameId: game.id }, { onSuccess: onDone })}
        >
          Not interested
        </Button>
      </Group>
      {(update.isError || remove.isError) && (
        <Text size="sm" c="red">
          {(update.error ?? remove.error)?.message}
        </Text>
      )}
    </Stack>
  )
}

function ChoiceCard({ choice, onDone }: { choice: BaseGameChoice; onDone: () => void }) {
  const update = useUpdateMyGame()
  const own = (gameId: number) =>
    update.mutate({ gameId, changes: { ownership: 'owned' } }, { onSuccess: onDone })
  const more = choice.option_count - choice.options.length

  return (
    <Card withBorder padding="sm">
      <Stack gap="xs">
        <Text size="sm">
          <b>{choice.expansion.name}</b> works with {plural(choice.option_count, 'game')}, and none
          of them is in your list as owned. Which do you have?
        </Text>
        {choice.options.map((option: GameSummary) => (
          <Group key={option.id} justify="space-between" wrap="nowrap">
            <Text size="sm">
              {option.name}
              {option.year_published && (
                <Text span c="dimmed" inherit>
                  {' '}
                  ({option.year_published})
                </Text>
              )}
            </Text>
            <Button
              size="compact-xs"
              variant="light"
              disabled={update.isPending}
              onClick={() => own(option.id)}
            >
              I own this
            </Button>
          </Group>
        ))}
        <Group gap="xs" align="center">
          <GameSearchSelect
            ariaLabel={`Search for the base game of ${choice.expansion.name}`}
            onPick={(game) => own(game.id)}
          />
          {more > 0 && (
            <Text size="xs" c="dimmed">
              or search the other {more}
            </Text>
          )}
        </Group>
        <Group>
          <Button size="xs" variant="subtle" color="gray" onClick={onDone}>
            Skip for now
          </Button>
        </Group>
        {update.isError && (
          <Text size="sm" c="red">
            {update.error.message}
          </Text>
        )}
      </Stack>
    </Card>
  )
}

/** A button that checks the user's owned expansions for base games missing from their list. */
export function FindMissingBaseGames() {
  const [opened, setOpened] = useState(false)
  const [done, setDone] = useState<Set<string>>(new Set())
  const find = useMutation({ mutationFn: findMissingBaseGames })
  const finish = (key: string) => setDone((current) => new Set(current).add(key))

  const open = () => {
    setDone(new Set())
    setOpened(true)
    find.mutate()
  }

  const suggestions = (find.data?.suggestions ?? []).filter((s) => !done.has(`s${s.game.id}`))
  const choices = (find.data?.choices ?? []).filter((c) => !done.has(`c${c.expansion.id}`))

  let body
  if (find.isPending) {
    body = (
      <Center py="lg">
        <Stack align="center" gap="xs">
          <Loader />
          <Text size="sm" c="dimmed">
            Checking your expansions…
          </Text>
        </Stack>
      </Center>
    )
  } else if (find.isError) {
    body = <Alert color="red">{find.error.message}</Alert>
  } else if (find.data) {
    const { unchecked, hidden } = find.data
    body = (
      <Stack>
        {suggestions.length === 0 && choices.length === 0 && (
          <Text>Every expansion you own has its base game in your list as owned.</Text>
        )}
        {suggestions.length > 0 && (
          <Text size="sm">
            You have expansions for {plural(suggestions.length, 'game')} you don&apos;t own:
          </Text>
        )}
        {suggestions.map((s) => (
          <SuggestionCard key={s.game.id} suggestion={s} onDone={() => finish(`s${s.game.id}`)} />
        ))}
        {choices.map((c) => (
          <ChoiceCard key={c.expansion.id} choice={c} onDone={() => finish(`c${c.expansion.id}`)} />
        ))}
        {unchecked > 0 && (
          <Text size="xs" c="dimmed">
            {plural(unchecked, 'expansion')} couldn&apos;t be checked with BGG yet. Try again in a
            minute.
          </Text>
        )}
        {hidden > 0 && (
          <Text size="xs" c="dimmed">
            {plural(hidden, 'game')} you said you&apos;re not interested in (or removed) aren&apos;t
            suggested.
          </Text>
        )}
      </Stack>
    )
  }

  return (
    <>
      <Button variant="default" onClick={open}>
        Find missing base games
      </Button>
      <Modal opened={opened} onClose={() => setOpened(false)} title="Missing base games" size="lg">
        {body}
      </Modal>
    </>
  )
}
