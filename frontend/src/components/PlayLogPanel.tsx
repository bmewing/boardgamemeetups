import {
  ActionIcon,
  Alert,
  Button,
  Card,
  Chip,
  Group,
  Modal,
  SegmentedControl,
  Stack,
  Switch,
  Text,
  Title,
} from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { useState } from 'react'

import type { Person } from '../api/friends'
import type { Meetup } from '../api/groups'
import { type PlayIn, type PlayLog, usePlayLog, useSavePlayLog } from '../api/votes'
import { GameSearchSelect } from './GameSearchSelect'
import { Grouper } from './mascot/Grouper'

type Draft = Omit<PlayIn, 'players' | 'winners'> & {
  key: number // stays put while plays are added, moved and removed
  name: string
  players: string[]
  winners: string[]
}
let lastKey = 0
const newKey = () => ++lastKey

/** "Azul", or "Azul · round 2" when a game was played more than once that night. */
function titles(plays: { game_id: number; name: string }[]): string[] {
  const seen = new Map<number, number>()
  return plays.map((p) => {
    const round = (seen.get(p.game_id) ?? 0) + 1
    seen.set(p.game_id, round)
    const repeated = plays.filter((q) => q.game_id === p.game_id).length > 1
    return repeated ? `${p.name} · round ${round}` : p.name
  })
}
const names = (people: { display_name: string }[]) => people.map((p) => p.display_name).join(', ')
const COOP_RESULTS = [
  { value: 'won', label: 'We won' },
  { value: 'lost', label: 'We lost' },
  { value: 'unknown', label: 'Not recorded' },
]

function startingDraft(log: PlayLog): { attendees: string[]; plays: Draft[] } {
  if (log.logged) {
    return {
      attendees: log.attendees.map((p) => p.id),
      plays: log.plays.map((p) => ({
        key: newKey(),
        game_id: p.game.id,
        name: p.game.name,
        coop: p.coop,
        coop_won: p.coop_won,
        players: p.players.map((x) => x.id),
        winners: p.winners.map((x) => x.id),
      })),
    }
  }
  const attendees = log.suggested_attendees.map((p) => p.id)
  return {
    attendees,
    plays: log.suggested_games.map((g) => ({
      key: newKey(),
      game_id: g.game.id,
      name: g.game.name,
      coop: g.coop,
      coop_won: null,
      players: attendees,
      winners: [],
    })),
  }
}

function LogEditor({
  meetup,
  log,
  members,
  onDone,
}: {
  meetup: Meetup
  log: PlayLog
  members: Person[]
  onDone: () => void
}) {
  const save = useSavePlayLog(meetup.id)
  const start = startingDraft(log)
  const [attendees, setAttendees] = useState<string[]>(start.attendees)
  const [plays, setPlays] = useState<Draft[]>(start.plays)
  const came = members.filter((m) => attendees.includes(m.id))
  const change = (i: number, changes: Partial<Draft>) =>
    setPlays((all) => all.map((p, j) => (j === i ? { ...p, ...changes } : p)))
  const move = (i: number, by: -1 | 1) =>
    setPlays((all) => {
      const next = [...all]
      ;[next[i], next[i + by]] = [next[i + by], next[i]]
      return next
    })
  const playAgain = (i: number) =>
    setPlays((all) => [
      ...all.slice(0, i + 1),
      { ...all[i], key: newKey(), coop_won: null, winners: [] },
      ...all.slice(i + 1),
    ])
  const title = titles(plays)

  return (
    <Stack>
      <Stack gap={4}>
        <Text size="sm" fw={500}>
          Who came?
        </Text>
        <Chip.Group
          multiple
          value={attendees}
          onChange={(ids) => {
            setAttendees(ids)
            // Nobody plays or wins without having come.
            setPlays((all) =>
              all.map((p) => ({
                ...p,
                players: p.players.filter((x) => ids.includes(x)),
                winners: p.winners.filter((x) => ids.includes(x)),
              })),
            )
          }}
        >
          <Group gap={6}>
            {members.map((m) => (
              <Chip key={m.id} value={m.id} size="sm">
                {m.display_name}
              </Chip>
            ))}
          </Group>
        </Chip.Group>
      </Stack>

      {plays.map((p, i) => (
        <Card key={p.key} withBorder padding="sm">
          <Stack gap="xs">
            <Group justify="space-between">
              <Text fw={600}>
                {i + 1}. {title[i]}
              </Text>
              <Group gap={4}>
                <Switch
                  size="xs"
                  label="Co-op"
                  checked={p.coop}
                  onChange={(e) =>
                    change(i, { coop: e.currentTarget.checked, coop_won: null, winners: [] })
                  }
                />
                <Button size="xs" variant="subtle" onClick={() => playAgain(i)}>
                  Played again
                </Button>
                <ActionIcon
                  variant="subtle"
                  color="gray"
                  aria-label={`Move ${title[i]} earlier`}
                  disabled={i === 0}
                  onClick={() => move(i, -1)}
                >
                  ↑
                </ActionIcon>
                <ActionIcon
                  variant="subtle"
                  color="gray"
                  aria-label={`Move ${title[i]} later`}
                  disabled={i === plays.length - 1}
                  onClick={() => move(i, 1)}
                >
                  ↓
                </ActionIcon>
                <ActionIcon
                  variant="subtle"
                  color="gray"
                  aria-label={`Remove ${title[i]}`}
                  onClick={() => setPlays((all) => all.filter((_, j) => j !== i))}
                >
                  ✕
                </ActionIcon>
              </Group>
            </Group>
            <Text size="xs" c="dimmed">
              Who played
            </Text>
            <Chip.Group
              multiple
              value={p.players}
              onChange={(ids) =>
                change(i, {
                  players: ids,
                  winners: p.winners.filter((w) => ids.includes(w)),
                })
              }
            >
              <Group gap={6}>
                {came.map((m) => (
                  <Chip key={m.id} value={m.id} size="xs">
                    {m.display_name}
                  </Chip>
                ))}
              </Group>
            </Chip.Group>
            {p.coop ? (
              <SegmentedControl
                size="xs"
                value={
                  p.coop_won === null || p.coop_won === undefined
                    ? 'unknown'
                    : p.coop_won
                      ? 'won'
                      : 'lost'
                }
                onChange={(v) => change(i, { coop_won: v === 'unknown' ? null : v === 'won' })}
                data={COOP_RESULTS}
              />
            ) : (
              <>
                <Text size="xs" c="dimmed">
                  Who won
                </Text>
                <Chip.Group
                  multiple
                  value={p.winners}
                  onChange={(ids) => change(i, { winners: ids })}
                >
                  <Group gap={6}>
                    {came
                      .filter((m) => p.players.includes(m.id))
                      .map((m) => (
                        <Chip key={m.id} value={m.id} size="xs" color="meeple">
                          {m.display_name}
                        </Chip>
                      ))}
                  </Group>
                </Chip.Group>
              </>
            )}
          </Stack>
        </Card>
      ))}

      <Stack gap={4}>
        <Text size="sm" fw={500}>
          Add a game we played
        </Text>
        <Text size="xs" c="dimmed">
          Openers, fillers, wrap-ups: add each game in the order you played it. Use “Played again”
          for another round of the same game.
        </Text>
        <GameSearchSelect
          ariaLabel="Add a game we played"
          onPick={(game) =>
            setPlays((all) => [
              ...all,
              {
                key: newKey(),
                game_id: game.id,
                name: game.name,
                coop: false,
                coop_won: null,
                players: attendees,
                winners: [],
              },
            ])
          }
        />
      </Stack>
      {save.isError && <Alert color="red">{save.error.message}</Alert>}
      <Group justify="flex-end">
        <Button
          loading={save.isPending}
          onClick={() =>
            save.mutate(
              {
                attendees,
                plays: plays.map(({ key: _key, name: _name, ...play }) => play),
              },
              { onSuccess: onDone },
            )
          }
        >
          Save
        </Button>
      </Group>
    </Stack>
  )
}

function result(play: PlayLog['plays'][number]): string {
  if (play.coop) {
    return play.coop_won === null ? 'Co-op' : play.coop_won ? 'Co-op · won' : 'Co-op · lost'
  }
  return play.winners.length ? `${names(play.winners)} won` : 'No winner recorded'
}

/** What was played, once the date has started; the owner and admins log it. */
export function PlayLogPanel({ meetup, members }: { meetup: Meetup; members: Person[] }) {
  const [now] = useState(() => Date.now())
  const started = new Date(meetup.starts_at).getTime() <= now
  const log = usePlayLog(meetup.id, started && meetup.status !== 'cancelled')
  const [editing, { open, close }] = useDisclosure(false)
  if (!started || meetup.status === 'cancelled' || !log.data) {
    return log.isError ? <Alert color="red">{log.error.message}</Alert> : null
  }
  const data = log.data
  if (!data.logged && !data.can_log) return null
  const playedTitles = titles(data.plays.map((p) => ({ game_id: p.game.id, name: p.game.name })))
  // Greg brings out the trophy once someone, or the whole table in a co-op, has a win logged.
  const someoneWon = data.logged && data.plays.some((p) => (p.coop ? p.coop_won : p.winners.length))

  return (
    <Stack gap="xs">
      <Group justify="space-between">
        <Group gap="xs" wrap="nowrap">
          {someoneWon && <Grouper pose="winner" size={64} label="" style={{ margin: '-10px 0' }} />}
          <Title order={4}>What we played</Title>
        </Group>
        {data.can_log && (
          <Button size="xs" variant={data.logged ? 'subtle' : 'filled'} onClick={open}>
            {data.logged ? 'Edit' : 'Log what we played'}
          </Button>
        )}
      </Group>
      {data.assumed && (
        <Text size="xs" c="dimmed">
          Nobody logged this date within a week, so it’s taken as the pick, played by everyone who
          said they were going.
        </Text>
      )}
      {data.logged ? (
        <>
          <Text size="sm">
            {data.attendees.length > 0
              ? `Came: ${names(data.attendees)}`
              : 'Nobody recorded as coming'}
          </Text>
          {data.plays.map((p, i) => (
            <Card key={i} withBorder padding="xs">
              <Text fw={600}>
                {data.plays.length > 1 && `${i + 1}. `}
                {playedTitles[i]}
              </Text>
              <Text size="sm">{result(p)}</Text>
              <Text size="xs" c="dimmed">
                Played by {names(p.players) || 'nobody recorded'}
              </Text>
            </Card>
          ))}
          {data.plays.length === 0 && <Text size="sm">No games recorded.</Text>}
        </>
      ) : (
        <Text size="sm" c="dimmed">
          Not logged yet. Without a log, a week after the date the pick counts as played by everyone
          who said they were going.
        </Text>
      )}
      <Modal opened={editing} onClose={close} title="What we played" size="lg">
        {editing && <LogEditor meetup={meetup} log={data} members={members} onDone={close} />}
      </Modal>
    </Stack>
  )
}
