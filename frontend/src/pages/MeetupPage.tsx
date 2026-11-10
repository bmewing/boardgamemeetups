import {
  Alert,
  Anchor,
  Badge,
  Button,
  Card,
  Center,
  Chip,
  Group,
  Loader,
  Menu,
  Modal,
  NumberInput,
  SegmentedControl,
  Select,
  Stack,
  Text,
  Title,
} from '@mantine/core'
import { useDebouncedValue, useDisclosure } from '@mantine/hooks'
import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'

import { useMoods } from '../api/collection'
import type { Person } from '../api/friends'
import {
  downloadMeetupCalendar,
  type Meetup,
  type Rsvp,
  type RsvpIn,
  type RsvpResponse,
  runsGroup,
  useDeleteMeetup,
  useMeetup,
  useMeetupGames,
  useRsvp,
  useUpdateMeetup,
} from '../api/groups'
import { BgaInfo } from '../components/BgaInfo'
import { GameCard } from '../components/GameCard'
import { Grouper } from '../components/mascot/Grouper'
import { ErrorNote, LoadingNote, MascotNote } from '../components/mascot/MascotNote'
import { widenedLabel } from '../components/gameFacts'
import {
  endTime,
  formatLongDate,
  formatTime,
  fromInputTime,
  googleCalendarUrl,
  pickMoods,
  toInputTime,
  withGuests,
} from '../components/meetupFormat'
import { MeetupForm } from '../components/MeetupForm'
import { VotePanel } from '../components/VotePanel'
import { useNominate, useVote } from '../api/votes'
import { PlayLogPanel } from '../components/PlayLogPanel'
import { RecapPanel } from '../components/rpg/RecapPanel'
import { ReasonChips } from '../components/Rollup'
import { lengthLabel, minutesTonight } from '../components/rollupFormat'
import { plural } from '../components/userGameFields'
import { PlayerPiece } from '../components/pieces/PlayerPiece'
import { UnlockHint } from '../components/achievements/UnlockHint'

const browserTimeZone = Intl.DateTimeFormat().resolvedOptions().timeZone

type Attendee = {
  person: Person
  guests?: number
  moods?: string[]
  bga_username?: string | null // at an online date
  bga_premium?: boolean
}

function useMoodNames() {
  const moods = useMoods()
  return new Map((moods.data ?? []).map((m) => [m.id, m.name]))
}

function People({ title, people }: { title: string; people: Attendee[] }) {
  const moodNames = useMoodNames()
  if (people.length === 0) return null
  const guests = people.reduce((sum, p) => sum + (p.guests ?? 0), 0)
  return (
    <Stack gap={4}>
      <Text size="sm" fw={500}>
        {withGuests(title, people.length, guests)}
      </Text>
      <Group gap="xs" align="flex-start">
        {people.map(({ person: p, guests: brings = 0, moods = [], bga_username, bga_premium }) => (
          <Anchor key={p.id} component={Link} to={`/people/${p.id}`} c="inherit">
            <Group gap={6} wrap="nowrap" align="flex-start">
              <PlayerPiece person={p} size={26} label="" />
              <Stack gap={0}>
                <Text size="sm">
                  {p.display_name}
                  {brings > 0 && ` +${brings}`}
                </Text>
                {moods.length > 0 && (
                  <Text size="xs" c="dimmed">
                    {moods.map((m) => moodNames.get(m) ?? m).join(', ')}
                  </Text>
                )}
                {bga_username && (
                  <Text size="xs" c="dimmed">
                    BGA: {bga_username}
                    {bga_premium && ' (Premium)'}
                  </Text>
                )}
              </Stack>
            </Group>
          </Anchor>
        ))}
      </Group>
    </Stack>
  )
}

/** How many of the people who might come are in each mood, most popular first. */
function MoodSummary({ rsvps }: { rsvps: Rsvp[] }) {
  const moodNames = useMoodNames()
  const counts = new Map<string, number>()
  for (const r of rsvps) {
    if (r.response === 'no') continue
    for (const m of r.moods) counts.set(m, (counts.get(m) ?? 0) + 1)
  }
  if (counts.size === 0) return null
  const sorted = [...counts].sort((a, b) => b[1] - a[1])
  return (
    <Text size="sm">
      <Text span fw={500}>
        In the mood for:{' '}
      </Text>
      {sorted.map(([m, n]) => `${moodNames.get(m) ?? m}${n > 1 ? ` ×${n}` : ''}`).join(' · ')}
    </Text>
  )
}

const guestLabel = (n: number) => (n === 0 ? 'Just me' : `Me + ${n}`)

function Answer({ meetup, onGoing }: { meetup: Meetup; onGoing?: () => void }) {
  const rsvp = useRsvp(meetup.id)
  const moods = useMoods()
  if (meetup.status === 'cancelled') return null

  // While a change is saving, show it rather than the answer it replaces.
  const saved = {
    response: meetup.my_response,
    guests: meetup.my_guests,
    moods: meetup.my_moods,
  }
  const current = rsvp.isPending && rsvp.variables ? rsvp.variables : saved
  const save = (changes: Partial<RsvpIn>) => {
    const next = { ...current, ...changes }
    if (!next.response) return
    const nowGoing = next.response === 'yes' && saved.response !== 'yes'
    rsvp.mutate({ ...next, response: next.response }, { onSuccess: () => nowGoing && onGoing?.() })
  }
  const mightCome = current.response === 'yes' || current.response === 'maybe'
  const limit = meetup.group.plus_one_limit

  return (
    <Stack gap="sm">
      <Stack gap={4}>
        <Text size="sm" fw={500}>
          Are you coming?
        </Text>
        {!saved.response && <UnlockHint achievement="rsvp_yes" text="say you're going" />}
        <SegmentedControl
          fullWidth
          value={current.response ?? ''}
          onChange={(value) => save({ response: value as RsvpResponse })}
          data={[
            { value: 'yes', label: 'Going' },
            { value: 'maybe', label: 'Maybe' },
            { value: 'no', label: "Can't go" },
          ]}
        />
      </Stack>
      {mightCome && limit > 0 && (
        <Select
          label="Bringing anyone?"
          description={`Each member can bring up to ${plural(limit, 'guest')}.`}
          allowDeselect={false}
          value={String(current.guests ?? 0)}
          onChange={(value) => save({ guests: Number(value ?? 0) })}
          data={Array.from({ length: limit + 1 }, (_, n) => ({
            value: String(n),
            label: guestLabel(n),
          }))}
        />
      )}
      {/* Moods are about which games to play, so RPG groups skip them. */}
      {mightCome && moods.data && meetup.group.kind === 'board_games' && (
        <Stack gap={4}>
          <Text size="sm" fw={500}>
            What are you in the mood for?
          </Text>
          <Chip.Group
            multiple
            value={current.moods ?? []}
            onChange={(picked) => save({ moods: pickMoods(current.moods ?? [], picked) })}
          >
            <Group gap={6}>
              {moods.data.map((m) => (
                <Chip key={m.id} value={m.id} size="sm" title={m.description}>
                  {m.name}
                </Chip>
              ))}
            </Group>
          </Chip.Group>
        </Stack>
      )}
      {rsvp.isError && (
        <Text size="sm" c="red">
          {rsvp.error.message}
        </Text>
      )}
    </Stack>
  )
}

function AddToCalendar({ meetup }: { meetup: Meetup }) {
  const [error, setError] = useState<string | null>(null)
  if (meetup.status === 'cancelled') return null
  return (
    <Group gap="xs">
      <Menu position="bottom-start" withinPortal>
        <Menu.Target>
          <Button size="xs" variant="light">
            Add to calendar
          </Button>
        </Menu.Target>
        <Menu.Dropdown>
          <Menu.Item
            onClick={() => {
              setError(null)
              downloadMeetupCalendar(meetup.id).catch((e: Error) => setError(e.message))
            }}
          >
            Download (.ics, any calendar app)
          </Menu.Item>
          <Menu.Item
            component="a"
            href={googleCalendarUrl({ ...meetup, title: meetup.group.name })}
            target="_blank"
            rel="noreferrer"
          >
            Google Calendar
          </Menu.Item>
        </Menu.Dropdown>
      </Menu>
      <Anchor component={Link} to="/groups#calendar" size="xs">
        Or subscribe to all your dates
      </Anchor>
      {error && (
        <Text size="sm" c="red">
          {error}
        </Text>
      )}
    </Group>
  )
}

const TOP_GAMES = 10
const MAX_PLAYERS = 30

/** What the filters are doing, in words, or null when the list is the default one. */
function filterSummary(players: number, confirmed: number, maxMinutes: number | null) {
  const parts: string[] = []
  if (players !== confirmed) parts.push(`fitted to ${plural(players, 'player')}`)
  if (maxMinutes !== null) parts.push(`${maxMinutes} min or less`)
  return parts.length > 0 ? parts.join(', ') : null
}

function FittingGames({ meetup }: { meetup: Meetup }) {
  // Just for whoever's looking: never saved, gone when they leave the page.
  const [players, setPlayers] = useState<number | null>(null)
  const [maxMinutes, setMaxMinutes] = useState<number | null>(null)
  const [typedPlayers] = useDebouncedValue(players, 300)
  // Clearing it goes back at once; typing a count waits for a pause.
  const games = useMeetupGames(meetup.id, players === null ? null : typedPlayers)
  const vote = useVote(meetup.id)
  const nominate = useNominate(meetup.id)
  const nominated = new Set(vote.data?.nominations.map((n) => n.game.id))
  const [showAll, setShowAll] = useState(false)
  if (meetup.status === 'cancelled') return null
  if (games.isPending) {
    return (
      <Center py="md">
        <Loader size="sm" />
      </Center>
    )
  }
  if (games.isError) return <Alert color="red">{games.error.message}</Alert>

  const {
    confirmed,
    guests,
    willing_to_split: split,
    unknown_player_count: unknown,
    online,
    premium_host_going: premiumHostGoing,
  } = games.data
  const fittedTo = games.data.players
  const fitting = games.data.games
  const ranked =
    maxMinutes === null
      ? fitting
      : fitting.filter((g) => {
          const minutes = minutesTonight(g.rollup)
          return minutes === null || minutes <= maxMinutes
        })
  const tooLong = fitting.length - ranked.length
  const shown = showAll ? ranked : ranked.slice(0, TOP_GAMES)
  const filtered = filterSummary(fittedTo, confirmed, maxMinutes)
  const reset = () => {
    setPlayers(null)
    setMaxMinutes(null)
  }
  return (
    <Stack gap="xs">
      <Title order={4}>Recommended games</Title>
      {confirmed === 0 ? (
        <Text size="sm" c="dimmed">
          {online
            ? "Once people say they're going, games on Board Game Arena they know that fit the group show here."
            : "Once people say they're going, games they'll bring that fit the group show here."}
        </Text>
      ) : (
        <>
          <Text size="sm" c="dimmed">
            {online
              ? 'On Board Game Arena, from the games the members going have, for '
              : 'Brought by the members going, for '}
            {plural(fittedTo, 'player')}
            {fittedTo !== confirmed
              ? ` (${confirmed} going)`
              : guests > 0 && ` (${plural(guests, 'guest')} included)`}
            :{' '}
            {split
              ? 'one table of everyone, or tables that leave nobody on their own'
              : 'everyone at one table'}
            . Ranked by what the people going think of them.
            {unknown > 0 &&
              ` ${plural(unknown, 'game')} left out because BGG hasn't said how many it seats.`}
            {online && ' Any other game on BGA can be nominated from the vote.'}
          </Text>
          <Group align="flex-end" gap="sm">
            <NumberInput
              label="Players"
              description="What if more or fewer came?"
              placeholder={String(confirmed)}
              min={1}
              max={MAX_PLAYERS}
              clampBehavior="strict"
              allowDecimal={false}
              w={170}
              value={players ?? ''}
              onChange={(v) => setPlayers(typeof v === 'number' ? v : null)}
            />
            <NumberInput
              label="Longest game"
              description="Minutes, teaching included"
              placeholder="Any length"
              min={15}
              max={24 * 60}
              step={15}
              allowDecimal={false}
              w={170}
              value={maxMinutes ?? ''}
              onChange={(v) => setMaxMinutes(typeof v === 'number' && v > 0 ? v : null)}
            />
          </Group>
          {filtered && (
            <Alert color="yellow" variant="light" p="xs">
              <Group justify="space-between" gap="xs">
                <Text size="sm">
                  Filtered just for you: {filtered}
                  {tooLong > 0 && ` (${plural(tooLong, 'longer game')} hidden)`}.
                </Text>
                <Button size="compact-xs" variant="white" color="yellow" onClick={reset}>
                  Back to who's going
                </Button>
              </Group>
            </Alert>
          )}
          {ranked.length === 0 && (
            <Text size="sm">
              {online
                ? 'Nothing on BGA the people going have fits '
                : "Nothing anyone's bringing fits "}
              {plural(fittedTo, 'player')}
              {maxMinutes !== null && ` in ${maxMinutes} min`}.
            </Text>
          )}
          {shown.map((g) => {
            const length = lengthLabel(g.rollup)
            const widened = widenedLabel(g.game, g)
            return (
              <GameCard
                key={g.game.id}
                game={g.game}
                // In the footer, so tapping it doesn't also open the game's page.
                below={
                  vote.data?.can_vote ? (
                    <Group>
                      <Button
                        size="xs"
                        variant="light"
                        disabled={nominated.has(g.game.id)}
                        loading={nominate.isPending && nominate.variables === g.game.id}
                        onClick={() => nominate.mutate(g.game.id)}
                      >
                        {nominated.has(g.game.id) ? 'Nominated' : 'Nominate'}
                      </Button>
                    </Group>
                  ) : undefined
                }
              >
                <Group gap="xs">
                  {g.bga ? (
                    <BgaInfo bga={g.bga} premiumHostGoing={premiumHostGoing} />
                  ) : (
                    <Text size="sm">
                      Brought by {g.bringers.map((p) => p.display_name).join(', ')}
                    </Text>
                  )}
                  {g.fit === 'split' && (
                    <Badge size="xs" variant="light" color="meeple">
                      One of several tables
                    </Badge>
                  )}
                </Group>
                {g.expansions.length > 0 && (
                  <Text size="xs" c="dimmed">
                    With {g.expansions.map((e) => e.name).join(', ')}
                    {widened && ` (${widened})`}
                  </Text>
                )}
                {length && (
                  <Text size="xs" c="dimmed">
                    {length}
                  </Text>
                )}
                <ReasonChips reasons={g.reasons} />
              </GameCard>
            )
          })}
          {ranked.length > TOP_GAMES && (
            <Group>
              <Button size="xs" variant="subtle" onClick={() => setShowAll((v) => !v)}>
                {showAll ? `Show the top ${TOP_GAMES}` : `Show all ${ranked.length}`}
              </Button>
            </Group>
          )}
        </>
      )}
    </Stack>
  )
}

function Organize({ meetup }: { meetup: Meetup }) {
  const [editing, { open, close }] = useDisclosure(false)
  const update = useUpdateMeetup(meetup.id)
  const remove = useDeleteMeetup(meetup.id, meetup.group.id)
  const navigate = useNavigate()
  const cancelled = meetup.status === 'cancelled'

  return (
    <>
      <Group gap="xs">
        <Button size="xs" variant="default" onClick={open}>
          Edit
        </Button>
        <Menu position="bottom-end" withinPortal>
          <Menu.Target>
            <Button size="xs" variant="subtle" color="gray" aria-label="More">
              ⋯
            </Button>
          </Menu.Target>
          <Menu.Dropdown>
            <Menu.Item
              color={cancelled ? undefined : 'red'}
              onClick={() => update.mutate({ status: cancelled ? 'scheduled' : 'cancelled' })}
            >
              {cancelled ? 'Put this date back on' : 'Cancel this date'}
            </Menu.Item>
            {!meetup.scheduled && (
              <Menu.Item
                color="red"
                onClick={() =>
                  remove.mutate(undefined, {
                    onSuccess: () => navigate(`/groups/${meetup.group.id}`, { replace: true }),
                  })
                }
              >
                Delete this date
              </Menu.Item>
            )}
          </Menu.Dropdown>
        </Menu>
      </Group>
      <Modal opened={editing} onClose={close} title="Edit this date">
        {meetup.scheduled && (
          <Text size="sm" c="dimmed" mb="sm">
            Changing the date, time, length or place keeps it this way even if the group's schedule
            changes later.
          </Text>
        )}
        <MeetupForm
          allowOnline={meetup.group.kind === 'board_games' || meetup.is_online}
          initial={{
            local_date: meetup.local_date,
            local_time: toInputTime(meetup.local_time),
            duration_minutes: meetup.duration_minutes,
            location: meetup.location ?? '',
            is_online: meetup.is_online,
            online_url: meetup.online_url ?? '',
            notes: meetup.notes ?? '',
          }}
          submitLabel="Save"
          busy={update.isPending}
          error={update.isError ? update.error.message : null}
          onSubmit={(f) => {
            // Send only what changed, so editing notes alone doesn't pin a scheduled date.
            const changes: Parameters<typeof update.mutate>[0] = {}
            if (f.local_date !== meetup.local_date) changes.local_date = f.local_date
            if (fromInputTime(f.local_time) !== meetup.local_time)
              changes.local_time = fromInputTime(f.local_time)
            if (f.duration_minutes !== meetup.duration_minutes)
              changes.duration_minutes = f.duration_minutes
            if (f.is_online !== meetup.is_online) changes.is_online = f.is_online
            if (!f.is_online && f.location !== (meetup.location ?? ''))
              changes.location = f.location
            if (f.is_online && f.online_url !== (meetup.online_url ?? ''))
              changes.online_url = f.online_url
            if (f.notes !== (meetup.notes ?? '')) changes.notes = f.notes
            update.mutate(changes, { onSuccess: close })
          }}
        />
      </Modal>
      {(update.isError || remove.isError) && !editing && (
        <Text size="sm" c="red">
          {(update.error ?? remove.error)?.message}
        </Text>
      )}
    </>
  )
}

// One loop of Greg's celebration.
const CHEER_MS = 4800

/** Greg cheers for one loop after a good moment, then goes back to dealing. */
function useCheer() {
  const [cheering, setCheering] = useState(false)
  const timer = useRef<number | undefined>(undefined)
  useEffect(() => {
    // Fetch the cheer now so the swap doesn't flash an empty frame.
    new Image().src = `${import.meta.env.BASE_URL}mascot/grouper-cheer.svg`
    return () => window.clearTimeout(timer.current)
  }, [])
  const cheer = useCallback(() => {
    setCheering(true)
    window.clearTimeout(timer.current)
    timer.current = window.setTimeout(() => setCheering(false), CHEER_MS)
  }, [])
  return [cheering, cheer] as const
}

export function MeetupPage() {
  const { meetupId = '' } = useParams()
  const meetup = useMeetup(meetupId)
  const [cheering, cheer] = useCheer()

  if (meetup.isPending) {
    return <LoadingNote>Setting up the table…</LoadingNote>
  }
  if (meetup.isError) return <ErrorNote error={meetup.error} onRetry={meetup.refetch} />
  if (meetup.data === null) {
    return (
      <MascotNote pose="think">
        <Text>This date doesn't exist, or it's in a group you're not in.</Text>
        <Anchor component={Link} to="/groups">
          Back to Groups
        </Anchor>
      </MascotNote>
    )
  }

  const m = meetup.data
  const by = (response: RsvpResponse) => m.rsvps.filter((r) => r.response === response)
  const elsewhere = m.group.time_zone !== browserTimeZone
  const rpg = m.group.kind === 'rpg'
  return (
    <Stack>
      <Anchor component={Link} to={`/groups/${m.group.id}`} size="sm">
        ← {m.group.name}
      </Anchor>
      <Group justify="space-between" align="flex-start">
        <Group gap="md" wrap="nowrap">
          <Grouper
            pose={m.status === 'cancelled' ? 'snooze' : cheering ? 'cheer' : 'deal'}
            size={96}
            label=""
          />
          <Stack gap={2}>
            <Title order={2} td={m.status === 'cancelled' ? 'line-through' : undefined}>
              {formatLongDate(m.local_date)}
            </Title>
            <Text>
              {formatTime(m.local_time)} – {endTime(m.local_time, m.duration_minutes)}
              {elsewhere && (
                <Text span c="dimmed" size="sm">
                  {' '}
                  ({m.group.time_zone} time)
                </Text>
              )}
            </Text>
            {m.is_online ? (
              <Group gap="xs">
                <Badge variant="light" color="meeple" tt="none">
                  Online · Board Game Arena
                </Badge>
                {m.online_url ? (
                  <Button
                    component="a"
                    href={m.online_url}
                    target="_blank"
                    rel="noreferrer"
                    size="compact-sm"
                  >
                    Join the table
                  </Button>
                ) : (
                  <Text size="sm" c="dimmed">
                    No table link yet
                  </Text>
                )}
              </Group>
            ) : (
              m.location && <Text c="dimmed">{m.location}</Text>
            )}
          </Stack>
        </Group>
        {runsGroup(m.my_role) && <Organize meetup={m} />}
      </Group>
      <AddToCalendar meetup={m} />
      {m.status === 'cancelled' && <Alert color="orange">This date is cancelled.</Alert>}
      {m.notes && (
        <Card withBorder padding="sm">
          <Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>
            {m.notes}
          </Text>
        </Card>
      )}
      <Answer meetup={m} onGoing={cheer} />
      <Stack gap="sm">
        <People title="Going" people={by('yes')} />
        <People title="Maybe" people={by('maybe')} />
        <People title="Can't go" people={by('no')} />
        <People title="Haven't said" people={m.no_answer.map((person) => ({ person }))} />
        {!rpg && <MoodSummary rsvps={m.rsvps} />}
      </Stack>
      {rpg ? (
        <RecapPanel meetup={m} />
      ) : (
        <>
          <PlayLogPanel meetup={m} members={[...m.rsvps.map((r) => r.person), ...m.no_answer]} />
          <VotePanel meetup={m} onLocked={cheer} />
          <FittingGames meetup={m} />
        </>
      )}
    </Stack>
  )
}
