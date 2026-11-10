import {
  Alert,
  Anchor,
  Badge,
  Button,
  Card,
  Center,
  Group,
  Loader,
  Menu,
  Modal,
  NumberInput,
  Stack,
  Switch,
  Tabs,
  Text,
  Textarea,
  TextInput,
  Title,
} from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { type FormEvent, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'

import {
  type Group as GroupData,
  type MeetupBrief,
  type Member,
  runsGroup,
  type Schedule,
  useAddMeetup,
  useCancelGroupInvite,
  useChangeRole,
  useDeleteGroup,
  useGroup,
  useGroupGames,
  useInviteToGroup,
  useRemoveMember,
  useUpdateGroup,
} from '../api/groups'
import { useFriends } from '../api/friends'
import { useMe } from '../api/me'
import { useMoods } from '../api/collection'
import { GameCard } from '../components/GameCard'
import { widenedLabel } from '../components/gameFacts'
import { RollupFacts } from '../components/Rollup'
import {
  formatDuration,
  formatShortDate,
  formatTime,
  fromInputTime,
  ROLE_LABELS,
  scheduleLabel,
  todayIso,
  toInputTime,
  placeLabel,
} from '../components/meetupFormat'
import { AddFriendButton } from '../components/AddFriendButton'
import { MeetupForm } from '../components/MeetupForm'
import { PersonPicker } from '../components/PersonPicker'
import { PersonRow } from '../components/PersonRow'
import { ScheduleEditor } from '../components/ScheduleEditor'
import { ErrorNote, LoadingNote, MascotNote } from '../components/mascot/MascotNote'
import { tableFit } from '../components/tableFit'
import { TimeZoneSelect } from '../components/TimeZoneSelect'
import { UnlockHint } from '../components/achievements/UnlockHint'

const RESPONSE_LABELS = { yes: 'Going', maybe: 'Maybe', no: "Can't go" } as const

function MeetupRow({ meetup }: { meetup: MeetupBrief }) {
  const cancelled = meetup.status === 'cancelled'
  return (
    <Card component={Link} to={`/meetups/${meetup.id}`} withBorder padding="sm">
      <Group justify="space-between" wrap="nowrap" align="flex-start">
        <Stack gap={2} style={{ minWidth: 0 }}>
          <Text fw={600} td={cancelled ? 'line-through' : undefined}>
            {formatShortDate(meetup.local_date)} · {formatTime(meetup.local_time)}
          </Text>
          <Text size="sm" c="dimmed" lineClamp={1}>
            {cancelled
              ? 'Cancelled'
              : `${meetup.headcount} going${meetup.maybe ? ` · ${meetup.maybe} maybe` : ''}${placeLabel(meetup) ? ` · ${placeLabel(meetup)}` : ''}`}
          </Text>
        </Stack>
        <Group gap={4} wrap="nowrap">
          {!meetup.scheduled && (
            <Badge size="xs" variant="light" color="grape">
              Extra date
            </Badge>
          )}
          {meetup.scheduled && meetup.edited && !cancelled && (
            <Badge size="xs" variant="light" color="orange">
              Changed
            </Badge>
          )}
          {meetup.my_response && !cancelled && (
            <Badge size="xs" variant="outline">
              {RESPONSE_LABELS[meetup.my_response]}
            </Badge>
          )}
        </Group>
      </Group>
    </Card>
  )
}

function DatesTab({ group }: { group: GroupData }) {
  const [adding, { open, close }] = useDisclosure(false)
  const add = useAddMeetup(group.id)
  const runs = runsGroup(group.my_role)

  return (
    <Stack>
      <Group justify="space-between" align="flex-start">
        <div>
          <Text fw={500}>{scheduleLabel(group.schedule)}</Text>
          <Text size="sm" c="dimmed">
            {formatTime(group.start_time)}, {formatDuration(group.duration_minutes)}
            {group.location ? ` · ${group.location}` : ''} · {group.time_zone}
          </Text>
        </div>
        {runs && (
          <Button size="xs" variant="default" onClick={open}>
            Add a date
          </Button>
        )}
      </Group>
      <Modal opened={adding} onClose={close} title="Add a date">
        <MeetupForm
          initial={{
            local_date: todayIso(),
            local_time: toInputTime(group.start_time),
            duration_minutes: group.duration_minutes,
            location: group.location ?? '',
            is_online: false,
            online_url: '',
            notes: '',
          }}
          submitLabel="Add"
          busy={add.isPending}
          error={add.isError ? add.error.message : null}
          onSubmit={(f) =>
            add.mutate(
              {
                local_date: f.local_date,
                local_time: fromInputTime(f.local_time),
                duration_minutes: f.duration_minutes,
                location: f.location || null,
                is_online: f.is_online,
                online_url: f.is_online ? f.online_url || null : null,
                notes: f.notes || null,
              },
              { onSuccess: close },
            )
          }
        />
      </Modal>
      {group.upcoming.length === 0 ? (
        <MascotNote pose="snooze" size={112}>
          <Text c="dimmed">
            No dates coming up.{' '}
            {runs ? 'Set a schedule in Settings, or add a date.' : 'The organizers will add some.'}
          </Text>
        </MascotNote>
      ) : (
        <Stack gap="xs">
          {group.upcoming.map((m) => (
            <MeetupRow key={m.id} meetup={m} />
          ))}
        </Stack>
      )}
      {group.recent.length > 0 && (
        <Stack gap="xs">
          <Title order={5} c="dimmed">
            Recent
          </Title>
          {group.recent.map((m) => (
            <MeetupRow key={m.id} meetup={m} />
          ))}
        </Stack>
      )}
    </Stack>
  )
}

function MemberMenu({ group, member, meId }: { group: GroupData; member: Member; meId: string }) {
  const change = useChangeRole(group.id)
  const remove = useRemoveMember(group.id)
  const isOwner = group.my_role === 'owner'
  const canRemove =
    member.person.id !== meId &&
    member.role !== 'owner' &&
    (isOwner || (group.my_role === 'admin' && member.role === 'member'))
  const canPromote = isOwner && member.role !== 'owner'
  if (!canRemove && !canPromote) return null

  const name = member.person.display_name
  return (
    <Menu position="bottom-end" withinPortal>
      <Menu.Target>
        <Button size="compact-xs" variant="subtle" color="gray" aria-label={`Manage ${name}`}>
          ⋯
        </Button>
      </Menu.Target>
      <Menu.Dropdown>
        {canPromote && member.role === 'member' && (
          <Menu.Item onClick={() => change.mutate({ userId: member.person.id, role: 'admin' })}>
            Make admin
          </Menu.Item>
        )}
        {canPromote && member.role === 'admin' && (
          <Menu.Item onClick={() => change.mutate({ userId: member.person.id, role: 'member' })}>
            Make a regular member
          </Menu.Item>
        )}
        {canPromote && (
          <Menu.Item
            onClick={() => {
              if (window.confirm(`Hand ${group.name} over to ${name}? You'll become an admin.`)) {
                change.mutate({ userId: member.person.id, role: 'owner' })
              }
            }}
          >
            Hand the group over
          </Menu.Item>
        )}
        {canRemove && (
          <Menu.Item color="red" onClick={() => remove.mutate(member.person.id)}>
            Remove from group
          </Menu.Item>
        )}
      </Menu.Dropdown>
    </Menu>
  )
}

function MembersTab({ group }: { group: GroupData }) {
  const me = useMe()
  const invite = useInviteToGroup(group.id)
  const cancel = useCancelGroupInvite(group.id)
  const leave = useRemoveMember(group.id)
  const navigate = useNavigate()
  const runs = runsGroup(group.my_role)
  const meId = me.data?.id ?? ''

  const inGroup = Object.fromEntries(group.members.map((m) => [m.person.id, 'In group']))
  for (const i of group.invites) if (i.person) inGroup[i.person.id] = 'Invited'

  const friends = useFriends()
  const friendsToInvite = (friends.data?.friends ?? [])
    .map((f) => f.person)
    .filter((p) => !inGroup[p.id])

  const sent = invite.data
  return (
    <Stack>
      {runs && group.members.length < 4 && (
        <UnlockHint
          achievement="group_of_4"
          text={`invite ${4 - group.members.length} more to make a table of four`}
        />
      )}
      {runs && (
        <Stack gap="xs">
          <PersonPicker
            label="Invite someone"
            description="Their username, or any email address. They join once they accept."
            actionLabel="Invite"
            busy={invite.isPending}
            unavailable={inGroup}
            suggestions={friendsToInvite}
            onTyping={() => invite.reset()}
            onPick={(pick) => invite.mutate(pick)}
          />
          {sent && (
            <Alert color={sent.on_app ? 'green' : 'blue'}>
              {sent.on_app
                ? `Invited ${sent.invite.person?.display_name ?? 'them'}. They'll see it on their Groups page.`
                : `Nobody uses ${sent.invite.email} yet. The invite will be waiting when they sign up with it, so send them this site's address.`}
            </Alert>
          )}
          {invite.isError && <Alert color="red">{invite.error.message}</Alert>}
        </Stack>
      )}

      {runs && group.invites.length > 0 && (
        <Stack gap="xs">
          <Title order={5}>Invited</Title>
          {group.invites.map((i) => (
            <Group key={i.id} justify="space-between" wrap="nowrap">
              {i.person ? (
                <PersonRow person={i.person} note="Hasn't answered yet" />
              ) : (
                <Text size="sm">{i.email} (not signed up yet)</Text>
              )}
              <Button size="compact-xs" variant="subtle" onClick={() => cancel.mutate(i.id)}>
                Cancel
              </Button>
            </Group>
          ))}
        </Stack>
      )}

      <Stack gap="xs">
        <Title order={5}>Members</Title>
        {group.members.map((m) => (
          <PersonRow
            key={m.person.id}
            person={m.person}
            note={m.role === 'member' ? undefined : ROLE_LABELS[m.role]}
          >
            <AddFriendButton person={m.person} meId={meId} />
            <MemberMenu group={group} member={m} meId={meId} />
          </PersonRow>
        ))}
      </Stack>

      {group.my_role !== 'owner' && (
        <Group>
          <Button
            variant="subtle"
            color="red"
            loading={leave.isPending}
            onClick={() => {
              if (window.confirm(`Leave ${group.name}?`)) {
                leave.mutate(meId, { onSuccess: () => navigate('/groups', { replace: true }) })
              }
            }}
          >
            Leave group
          </Button>
        </Group>
      )}
      {(leave.isError || cancel.isError) && (
        <Alert color="red">{(leave.error ?? cancel.error)?.message}</Alert>
      )}
    </Stack>
  )
}

function GamesTab({ group }: { group: GroupData }) {
  const games = useGroupGames(group.id)
  const moods = useMoods()
  const moodNames = useMemo(
    () => new Map((moods.data ?? []).map((m) => [m.id, m.name])),
    [moods.data],
  )
  const [players, setPlayers] = useState<number | null>(null)
  const [name, setName] = useState('')

  const shown = useMemo(() => {
    const q = name.trim().toLowerCase()
    return (games.data ?? []).filter(
      (row) =>
        (!q || row.game.name.toLowerCase().includes(q)) &&
        (players === null ||
          tableFit(row.min_players, row.max_players, players, group.willing_to_split) !== null),
    )
  }, [games.data, name, players, group.willing_to_split])

  if (games.isPending) {
    return (
      <Center py="xl">
        <Loader />
      </Center>
    )
  }
  if (games.isError) return <Alert color="red">{games.error.message}</Alert>
  if (games.data.length === 0) {
    return <Text c="dimmed">Nobody in the group has added games they own yet.</Text>
  }
  return (
    <Stack>
      <Group grow>
        <TextInput label="Name" value={name} onChange={(e) => setName(e.currentTarget.value)} />
        <NumberInput
          label="Players"
          description={group.willing_to_split ? 'Split tables allowed' : 'All at one table'}
          min={1}
          max={30}
          value={players ?? ''}
          onChange={(v) => setPlayers(typeof v === 'number' ? v : null)}
        />
      </Group>
      <Text size="sm" c="dimmed">
        {shown.length} of {games.data.length} games
      </Text>
      <Stack gap="xs">
        {shown.map((row) => {
          const rated = row.answers.filter((a) => a.rating !== null)
          const widened = widenedLabel(row.game, row)
          return (
            <GameCard key={row.game.id} game={row.game}>
              <Text size="sm">Owned by {row.owners.map((p) => p.display_name).join(', ')}</Text>
              {row.expansions.length > 0 && (
                <Text size="xs" c="dimmed">
                  With {row.expansions.map((e) => e.name).join(', ')}
                  {widened && ` (${widened})`}
                </Text>
              )}
              <RollupFacts rollup={row.rollup} moodNames={moodNames} />
              {rated.length > 0 && (
                <Text size="xs" c="dimmed">
                  Ratings: {rated.map((a) => `${a.person.display_name} ${a.rating}`).join(' · ')}
                </Text>
              )}
            </GameCard>
          )
        })}
      </Stack>
    </Stack>
  )
}

function SettingsTab({ group }: { group: GroupData }) {
  const update = useUpdateGroup(group.id)
  const remove = useDeleteGroup(group.id)
  const navigate = useNavigate()
  const [name, setName] = useState(group.name)
  const [description, setDescription] = useState(group.description ?? '')
  const [timeZone, setTimeZone] = useState(group.time_zone)
  const [split, setSplit] = useState(group.willing_to_split)
  const [schedule, setSchedule] = useState<Schedule | null>(group.schedule)
  const [startTime, setStartTime] = useState(toInputTime(group.start_time))
  const [duration, setDuration] = useState(group.duration_minutes)
  const [location, setLocation] = useState(group.location ?? '')
  const [plusOnes, setPlusOnes] = useState(group.plus_one_limit)

  const save = (e: FormEvent) => {
    e.preventDefault()
    const fewerGuests = plusOnes < group.plus_one_limit
    if (
      fewerGuests &&
      !window.confirm(
        `Lower the guest limit to ${plusOnes}? Anyone bringing more to an upcoming date will be cut down to ${plusOnes}.`,
      )
    ) {
      return
    }
    update.mutate({
      name,
      description,
      time_zone: timeZone,
      willing_to_split: split,
      schedule,
      start_time: fromInputTime(startTime),
      duration_minutes: duration,
      location,
      plus_one_limit: plusOnes,
    })
  }

  return (
    <Stack gap="xl">
      <form onSubmit={save}>
        <Stack>
          <TextInput
            label="Name"
            required
            maxLength={80}
            value={name}
            onChange={(e) => setName(e.currentTarget.value)}
          />
          <Textarea
            label="Description"
            autosize
            minRows={2}
            value={description}
            onChange={(e) => setDescription(e.currentTarget.value)}
          />
          <Switch
            label="Happy to split into several tables"
            description="Then games that seat some of the people coming (leaving at least two for another table) are suggested too."
            checked={split}
            onChange={(e) => setSplit(e.currentTarget.checked)}
          />
          <NumberInput
            label="Guests each member can bring"
            description="0 means no guests. Guests count toward how many are playing."
            min={0}
            max={10}
            clampBehavior="strict"
            allowDecimal={false}
            value={plusOnes}
            onChange={(v) => setPlusOnes(typeof v === 'number' ? v : 0)}
          />
          <Title order={4}>When you meet</Title>
          <ScheduleEditor value={schedule} onChange={setSchedule} />
          <Group grow>
            <TextInput
              label="Usual start"
              type="time"
              required
              value={startTime}
              onChange={(e) => setStartTime(e.currentTarget.value)}
            />
            <NumberInput
              label="Length (minutes)"
              min={15}
              max={1440}
              step={30}
              value={duration}
              onChange={(v) => setDuration(typeof v === 'number' ? v : 180)}
            />
          </Group>
          <TextInput
            label="Usual place"
            maxLength={200}
            value={location}
            onChange={(e) => setLocation(e.currentTarget.value)}
          />
          <TimeZoneSelect
            value={timeZone}
            onChange={setTimeZone}
            description="Dates keep their local time here, through daylight saving changes."
          />
          <Text size="xs" c="dimmed">
            Saving updates every future date nobody has changed by hand. Dates you've moved, changed
            or cancelled stay as they are.
          </Text>
          {update.isError && <Alert color="red">{update.error.message}</Alert>}
          {update.isSuccess && !update.isPending && <Alert color="green">Saved</Alert>}
          <Group justify="flex-end">
            <Button type="submit" loading={update.isPending}>
              Save
            </Button>
          </Group>
        </Stack>
      </form>

      {group.my_role === 'owner' && (
        <Stack gap="xs">
          <Title order={4} c="red">
            Delete the group
          </Title>
          <Text size="sm" c="dimmed">
            Removes the group, its dates and everyone's answers about them, for all members.
          </Text>
          {remove.isError && <Alert color="red">{remove.error.message}</Alert>}
          <Group>
            <Button
              color="red"
              variant="light"
              loading={remove.isPending}
              onClick={() => {
                if (window.confirm(`Delete ${group.name} for everyone? This can't be undone.`)) {
                  remove.mutate(undefined, {
                    onSuccess: () => navigate('/groups', { replace: true }),
                  })
                }
              }}
            >
              Delete group
            </Button>
          </Group>
        </Stack>
      )}
    </Stack>
  )
}

export function GroupPage() {
  const { groupId = '' } = useParams()
  const group = useGroup(groupId)

  if (group.isPending) return <LoadingNote>Loading the group…</LoadingNote>
  if (group.isError) return <ErrorNote error={group.error} onRetry={group.refetch} />
  if (group.data === null) {
    return (
      <MascotNote pose="think">
        <Text>This group doesn't exist, or you're not in it.</Text>
        <Anchor component={Link} to="/groups">
          Back to Groups
        </Anchor>
      </MascotNote>
    )
  }

  const data = group.data
  return (
    <Stack>
      <div>
        <Group gap="xs">
          <Title order={2}>{data.name}</Title>
          {data.my_role !== 'member' && <Badge variant="light">{ROLE_LABELS[data.my_role]}</Badge>}
        </Group>
        {data.description && <Text c="dimmed">{data.description}</Text>}
      </div>
      <Tabs defaultValue="dates" keepMounted={false}>
        <Tabs.List>
          <Tabs.Tab value="dates">Dates</Tabs.Tab>
          <Tabs.Tab value="members">Members ({data.members.length})</Tabs.Tab>
          <Tabs.Tab value="games">Games</Tabs.Tab>
          {runsGroup(data.my_role) && <Tabs.Tab value="settings">Settings</Tabs.Tab>}
        </Tabs.List>
        <Tabs.Panel value="dates" pt="md">
          <DatesTab group={data} />
        </Tabs.Panel>
        <Tabs.Panel value="members" pt="md">
          <MembersTab group={data} />
        </Tabs.Panel>
        <Tabs.Panel value="games" pt="md">
          <GamesTab group={data} />
        </Tabs.Panel>
        {runsGroup(data.my_role) && (
          <Tabs.Panel value="settings" pt="md">
            <SettingsTab group={data} />
          </Tabs.Panel>
        )}
      </Tabs>
    </Stack>
  )
}
