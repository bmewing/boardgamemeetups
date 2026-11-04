import {
  Alert,
  Anchor,
  Badge,
  Button,
  Card,
  Checkbox,
  Group,
  Modal,
  Select,
  Stack,
  Text,
  Title,
} from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { useState } from 'react'
import { Link } from 'react-router'

import type { Meetup } from '../api/groups'
import { useMe } from '../api/me'
import {
  type Nomination,
  useBring,
  useCastVote,
  useLockPick,
  useNominate,
  useUnlockPick,
  useVote,
  useWithdraw,
  type VoteState,
} from '../api/votes'
import { plural } from './userGameFields'

const names = (people: { display_name: string }[]) => people.map((p) => p.display_name).join(', ')

function Ballot({ meetup, state }: { meetup: Meetup; state: VoteState }) {
  const nominate = useNominate(meetup.id)
  const castVote = useCastVote(meetup.id)
  const withdraw = useWithdraw(meetup.id)
  const error = nominate.error ?? castVote.error ?? withdraw.error

  return (
    <Stack gap="xs">
      <Text size="sm" c="dimmed">
        {state.can_vote
          ? 'Vote for every game you’d be happy to play. Nominate from the recommendations below, or any game someone going owns.'
          : 'People who said they’re going nominate and vote.'}
      </Text>
      {state.nominations.length === 0 && <Text size="sm">Nothing nominated yet.</Text>}
      {state.nominations.map((n) => (
        <Card key={n.id} withBorder padding="xs">
          <Group justify="space-between" wrap="nowrap">
            <Stack gap={0} style={{ minWidth: 0 }}>
              <Anchor component={Link} to={`/games/${n.game.id}`} fw={600} c="inherit">
                {n.game.name}
              </Anchor>
              <Text size="xs" c="dimmed">
                {n.votes.length > 0
                  ? `${plural(n.votes.length, 'vote')}: ${names(n.votes)}`
                  : 'No votes yet'}
              </Text>
            </Stack>
            <Group gap={4} wrap="nowrap">
              {state.can_vote && (
                <Button
                  size="xs"
                  variant={n.my_vote ? 'filled' : 'default'}
                  onClick={() => castVote.mutate({ nominationId: n.id, on: !n.my_vote })}
                >
                  {n.my_vote ? 'Voted' : 'Vote'}
                </Button>
              )}
              {n.can_remove && (
                <Button
                  size="xs"
                  variant="subtle"
                  color="gray"
                  onClick={() => withdraw.mutate(n.id)}
                  aria-label={`Take ${n.game.name} off`}
                >
                  ✕
                </Button>
              )}
            </Group>
          </Group>
        </Card>
      ))}
      {state.can_vote && state.nominatable.length > 0 && (
        <Select
          aria-label="Nominate another game"
          placeholder="Nominate another game someone going owns…"
          searchable
          value={null}
          data={state.nominatable.map((g) => ({ value: String(g.id), label: g.name }))}
          onChange={(value) => value && nominate.mutate(Number(value))}
        />
      )}
      {error && (
        <Text size="sm" c="red">
          {error.message}
        </Text>
      )}
    </Stack>
  )
}

function LockButton({ meetup, state }: { meetup: Meetup; state: VoteState }) {
  const [opened, { open, close }] = useDisclosure(false)
  const lock = useLockPick(meetup.id)
  const most = Math.max(0, ...state.nominations.map((n) => n.votes.length))
  const [chosen, setChosen] = useState<string[]>([])

  if (state.nominations.length === 0) return null
  return (
    <>
      <Button
        size="xs"
        variant="light"
        onClick={() => {
          // Start with the games that have the most votes.
          setChosen(state.nominations.filter((n) => n.votes.length === most).map((n) => n.id))
          open()
        }}
      >
        Lock the pick
      </Button>
      <Modal opened={opened} onClose={close} title="Lock the pick">
        <Stack>
          <Text size="sm" c="dimmed">
            Pick one game, or several for more than one table. Voting stops; people can still change
            whether they’re coming.
          </Text>
          <Checkbox.Group value={chosen} onChange={setChosen}>
            <Stack gap="xs">
              {state.nominations.map((n) => (
                <Checkbox
                  key={n.id}
                  value={n.id}
                  label={`${n.game.name} (${plural(n.votes.length, 'vote')})`}
                />
              ))}
            </Stack>
          </Checkbox.Group>
          {lock.isError && <Alert color="red">{lock.error.message}</Alert>}
          <Group justify="flex-end">
            <Button
              disabled={chosen.length === 0}
              loading={lock.isPending}
              onClick={() => lock.mutate(chosen, { onSuccess: close })}
            >
              Lock
            </Button>
          </Group>
        </Stack>
      </Modal>
    </>
  )
}

function Pick({ meetup, pick, meId }: { meetup: Meetup; pick: Nomination; meId?: string }) {
  const bring = useBring(meetup.id)
  const runs = meetup.my_role === 'owner' || meetup.my_role === 'admin'
  const info = pick.bring
  const bringer = info?.person
  const iOwnIt = info?.owners_going.some((o) => o.id === meId) ?? false

  return (
    <Card withBorder padding="sm">
      <Stack gap={6}>
        <Group gap="xs">
          <Anchor component={Link} to={`/games/${pick.game.id}`} fw={600} c="inherit">
            {pick.game.name}
          </Anchor>
          {!pick.fits_now && (
            <Badge size="sm" color="red" variant="light" tt="none">
              Doesn’t fit the people going any more
            </Badge>
          )}
        </Group>
        <Group gap="xs">
          {bringer ? (
            <Text size="sm">Brought by {bringer.display_name}</Text>
          ) : (
            <Badge color="orange" variant="light" tt="none">
              Nobody’s bringing it yet
            </Badge>
          )}
          {!bringer && iOwnIt && (
            <Button size="xs" onClick={() => bring.mutate({ gameId: pick.game.id })}>
              I’ll bring it
            </Button>
          )}
          {bringer?.id === meId && (
            <Button
              size="xs"
              variant="subtle"
              color="gray"
              onClick={() => bring.mutate({ gameId: pick.game.id, stop: true })}
            >
              I can’t bring it
            </Button>
          )}
          {runs && info && info.owners_going.length > 1 && (
            <Select
              size="xs"
              aria-label={`Who brings ${pick.game.name}`}
              placeholder="Choose who brings it"
              value={bringer?.id ?? null}
              data={info.owners_going.map((o) => ({ value: o.id, label: o.display_name }))}
              onChange={(value) => value && bring.mutate({ gameId: pick.game.id, userId: value })}
              w={180}
            />
          )}
        </Group>
        {info && !bringer && info.owners_going.length === 0 && (
          <Text size="xs" c="dimmed">
            Nobody going owns it now.
          </Text>
        )}
        {bring.isError && (
          <Text size="sm" c="red">
            {bring.error.message}
          </Text>
        )}
      </Stack>
    </Card>
  )
}

/** Nominating and voting on what to play, then the pick and who's bringing it. */
export function VotePanel({ meetup }: { meetup: Meetup }) {
  const vote = useVote(meetup.id)
  const unlock = useUnlockPick(meetup.id)
  const me = useMe()
  if (meetup.status === 'cancelled' || !vote.data) {
    return vote.isError ? <Alert color="red">{vote.error.message}</Alert> : null
  }
  const state = vote.data
  const picks = state.nominations.filter((n) => n.picked)
  const others = state.nominations.filter((n) => !n.picked)

  return (
    <Stack gap="xs">
      <Group justify="space-between">
        <Title order={4}>{state.locked ? 'The pick' : 'The vote'}</Title>
        {state.can_lock &&
          (state.locked ? (
            <Button
              size="xs"
              variant="subtle"
              loading={unlock.isPending}
              onClick={() => {
                if (window.confirm('Unlock the vote? The pick and who’s bringing it are cleared.'))
                  unlock.mutate()
              }}
            >
              Unlock
            </Button>
          ) : (
            <LockButton meetup={meetup} state={state} />
          ))}
      </Group>
      {state.locked ? (
        <>
          {picks.map((p) => (
            <Pick key={p.id} meetup={meetup} pick={p} meId={me.data?.id} />
          ))}
          {others.length > 0 && (
            <Text size="xs" c="dimmed">
              Also nominated: {others.map((n) => n.game.name).join(', ')}
            </Text>
          )}
        </>
      ) : (
        <Ballot meetup={meetup} state={state} />
      )}
      {unlock.isError && (
        <Text size="sm" c="red">
          {unlock.error.message}
        </Text>
      )}
    </Stack>
  )
}
