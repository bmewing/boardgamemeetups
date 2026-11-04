import {
  Alert,
  Anchor,
  Avatar,
  Badge,
  Button,
  Card,
  Center,
  Group,
  Loader,
  Menu,
  Modal,
  SegmentedControl,
  Stack,
  Text,
  Title,
} from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { Link, useNavigate, useParams } from 'react-router'

import type { Person } from '../api/friends'
import {
  type Meetup,
  type RsvpResponse,
  runsGroup,
  useDeleteMeetup,
  useMeetup,
  useMeetupGames,
  useRsvp,
  useUpdateMeetup,
} from '../api/groups'
import { GameCard } from '../components/GameCard'
import {
  endTime,
  formatLongDate,
  formatTime,
  fromInputTime,
  toInputTime,
} from '../components/meetupFormat'
import { MeetupForm } from '../components/MeetupForm'
import { plural } from '../components/userGameFields'

const browserTimeZone = Intl.DateTimeFormat().resolvedOptions().timeZone

function People({ title, people }: { title: string; people: Person[] }) {
  if (people.length === 0) return null
  return (
    <Stack gap={4}>
      <Text size="sm" fw={500}>
        {title} ({people.length})
      </Text>
      <Group gap="xs">
        {people.map((p) => (
          <Anchor key={p.id} component={Link} to={`/people/${p.id}`} c="inherit">
            <Group gap={6} wrap="nowrap">
              <Avatar
                src={p.avatar_url}
                name={p.display_name}
                color="initials"
                radius="xl"
                size="sm"
              />
              <Text size="sm">{p.display_name}</Text>
            </Group>
          </Anchor>
        ))}
      </Group>
    </Stack>
  )
}

function Answer({ meetup }: { meetup: Meetup }) {
  const rsvp = useRsvp(meetup.id)
  if (meetup.status === 'cancelled') return null
  return (
    <Stack gap={4}>
      <Text size="sm" fw={500}>
        Are you coming?
      </Text>
      <SegmentedControl
        fullWidth
        value={rsvp.isPending ? (rsvp.variables ?? '') : (meetup.my_response ?? '')}
        onChange={(value) => rsvp.mutate(value as RsvpResponse)}
        data={[
          { value: 'yes', label: 'Going' },
          { value: 'maybe', label: 'Maybe' },
          { value: 'no', label: "Can't go" },
        ]}
      />
      {rsvp.isError && (
        <Text size="sm" c="red">
          {rsvp.error.message}
        </Text>
      )}
    </Stack>
  )
}

function FittingGames({ meetup }: { meetup: Meetup }) {
  const games = useMeetupGames(meetup.id)
  if (meetup.status === 'cancelled') return null
  if (games.isPending) {
    return (
      <Center py="md">
        <Loader size="sm" />
      </Center>
    )
  }
  if (games.isError) return <Alert color="red">{games.error.message}</Alert>

  const { confirmed, willing_to_split: split, unknown_player_count: unknown } = games.data
  return (
    <Stack gap="xs">
      <Title order={4}>Games that fit</Title>
      {confirmed === 0 ? (
        <Text size="sm" c="dimmed">
          Once people say they're going, games they'll bring that fit the group show here.
        </Text>
      ) : (
        <>
          <Text size="sm" c="dimmed">
            Brought by the {plural(confirmed, 'person', 'people')} going, for{' '}
            {split
              ? 'one table of everyone, or tables that leave nobody on their own'
              : 'everyone at one table'}
            .
            {unknown > 0 &&
              ` ${plural(unknown, 'game')} left out because BGG hasn't said how many it seats.`}
          </Text>
          {games.data.games.length === 0 && (
            <Text size="sm">Nothing anyone's bringing fits {plural(confirmed, 'player')}.</Text>
          )}
          {games.data.games.map((g) => (
            <GameCard key={g.game.id} game={g.game}>
              <Group gap="xs">
                <Text size="sm">Brought by {g.bringers.map((p) => p.display_name).join(', ')}</Text>
                {g.fit === 'split' && (
                  <Badge size="xs" variant="light" color="teal">
                    One of several tables
                  </Badge>
                )}
              </Group>
            </GameCard>
          ))}
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
          initial={{
            local_date: meetup.local_date,
            local_time: toInputTime(meetup.local_time),
            duration_minutes: meetup.duration_minutes,
            location: meetup.location ?? '',
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
            if (f.location !== (meetup.location ?? '')) changes.location = f.location
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

export function MeetupPage() {
  const { meetupId = '' } = useParams()
  const meetup = useMeetup(meetupId)

  if (meetup.isPending) {
    return (
      <Center py="xl">
        <Loader />
      </Center>
    )
  }
  if (meetup.isError) return <Alert color="red">{meetup.error.message}</Alert>
  if (meetup.data === null) {
    return (
      <Stack>
        <Text>This date doesn't exist, or it's in a group you're not in.</Text>
        <Anchor component={Link} to="/groups">
          Back to Groups
        </Anchor>
      </Stack>
    )
  }

  const m = meetup.data
  const by = (response: RsvpResponse) =>
    m.rsvps.filter((r) => r.response === response).map((r) => r.person)
  const elsewhere = m.group.time_zone !== browserTimeZone
  return (
    <Stack>
      <Anchor component={Link} to={`/groups/${m.group.id}`} size="sm">
        ← {m.group.name}
      </Anchor>
      <Group justify="space-between" align="flex-start">
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
          {m.location && <Text c="dimmed">{m.location}</Text>}
        </Stack>
        {runsGroup(m.my_role) && <Organize meetup={m} />}
      </Group>
      {m.status === 'cancelled' && <Alert color="orange">This date is cancelled.</Alert>}
      {m.notes && (
        <Card withBorder padding="sm">
          <Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>
            {m.notes}
          </Text>
        </Card>
      )}
      <Answer meetup={m} />
      <Stack gap="sm">
        <People title="Going" people={by('yes')} />
        <People title="Maybe" people={by('maybe')} />
        <People title="Can't go" people={by('no')} />
        <People title="Haven't said" people={m.no_answer} />
      </Stack>
      <FittingGames meetup={m} />
    </Stack>
  )
}
