import {
  Alert,
  Badge,
  Button,
  Card,
  Center,
  Checkbox,
  Group,
  Loader,
  Modal,
  Stack,
  Text,
  Textarea,
  TextInput,
  Title,
} from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { type FormEvent, useState } from 'react'
import { Link, useNavigate } from 'react-router'

import {
  type GroupInviteForMe,
  type GroupSummary,
  useAnswerGroupInvite,
  useCreateGroup,
  useGroups,
} from '../api/groups'
import { useMe } from '../api/me'
import { formatShortDate, formatTime, ROLE_LABELS } from '../components/meetupFormat'
import { TimeZoneSelect } from '../components/TimeZoneSelect'
import { plural } from '../components/userGameFields'

function NewGroup({ opened, onClose }: { opened: boolean; onClose: () => void }) {
  const create = useCreateGroup()
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [split, setSplit] = useState(false)
  // Starts as your account's zone; null until you pick one, so a late-loading profile still wins.
  const me = useMe()
  const [picked, setPicked] = useState<string | null>(null)
  const timeZone = picked ?? me.data?.time_zone ?? 'UTC'

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return
    create.mutate(
      { name, description: description || null, willing_to_split: split, time_zone: timeZone },
      { onSuccess: (group) => navigate(`/groups/${group.id}`) },
    )
  }

  return (
    <Modal opened={opened} onClose={onClose} title="New group">
      <form onSubmit={submit}>
        <Stack>
          <TextInput
            label="Name"
            required
            maxLength={80}
            value={name}
            onChange={(e) => setName(e.currentTarget.value)}
            data-autofocus
          />
          <Textarea
            label="Description"
            autosize
            minRows={2}
            value={description}
            onChange={(e) => setDescription(e.currentTarget.value)}
          />
          <Checkbox
            label="Happy to split into several tables"
            description="Otherwise everyone plays one game together, so only games that seat everyone coming are suggested."
            checked={split}
            onChange={(e) => setSplit(e.currentTarget.checked)}
          />
          <TimeZoneSelect
            value={timeZone}
            onChange={setPicked}
            description="Dates keep their local time here, through daylight saving changes."
          />
          {create.isError && <Alert color="red">{create.error.message}</Alert>}
          <Group justify="flex-end">
            <Button type="submit" loading={create.isPending} disabled={!name.trim()}>
              Make the group
            </Button>
          </Group>
        </Stack>
      </form>
    </Modal>
  )
}

function InviteCard({ invite }: { invite: GroupInviteForMe }) {
  const answer = useAnswerGroupInvite()
  const navigate = useNavigate()
  const busy = answer.isPending
  return (
    <Card withBorder padding="md">
      <Stack gap="xs">
        <Text fw={600}>{invite.group_name}</Text>
        <Text size="sm" c="dimmed">
          {invite.invited_by ? `${invite.invited_by.display_name} invited you · ` : ''}
          {plural(invite.member_count, 'member')}
        </Text>
        {invite.group_description && <Text size="sm">{invite.group_description}</Text>}
        <Text size="xs" c="dimmed">
          Joining shares your games and your answers about them, but never your notes, with the
          group's members.
        </Text>
        {answer.isError && (
          <Text size="sm" c="red">
            {answer.error.message}
          </Text>
        )}
        <Group gap="xs">
          <Button
            size="xs"
            loading={busy && answer.variables?.accept}
            disabled={busy}
            onClick={() =>
              answer.mutate(
                { inviteId: invite.id, accept: true },
                { onSuccess: () => navigate(`/groups/${invite.group_id}`) },
              )
            }
          >
            Join
          </Button>
          <Button
            size="xs"
            variant="default"
            disabled={busy}
            onClick={() => answer.mutate({ inviteId: invite.id, accept: false })}
          >
            Decline
          </Button>
        </Group>
      </Stack>
    </Card>
  )
}

function GroupCard({ group }: { group: GroupSummary }) {
  const next = group.next_meetup
  return (
    <Card component={Link} to={`/groups/${group.id}`} withBorder padding="md">
      <Stack gap={4}>
        <Group justify="space-between" wrap="nowrap">
          <Text fw={600}>{group.name}</Text>
          {group.my_role !== 'member' && (
            <Badge size="sm" variant="light">
              {ROLE_LABELS[group.my_role]}
            </Badge>
          )}
        </Group>
        <Text size="sm" c="dimmed">
          {plural(group.member_count, 'member')}
          {next
            ? ` · Next: ${formatShortDate(next.local_date)}, ${formatTime(next.local_time)} · ${next.yes} going`
            : ' · No dates coming up'}
        </Text>
      </Stack>
    </Card>
  )
}

export function GroupsPage() {
  const groups = useGroups()
  const [creating, { open, close }] = useDisclosure(false)

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>Groups</Title>
        <Button onClick={open}>New group</Button>
      </Group>
      <NewGroup opened={creating} onClose={close} />

      {groups.isPending && (
        <Center py="xl">
          <Loader />
        </Center>
      )}
      {groups.isError && <Alert color="red">{groups.error.message}</Alert>}

      {groups.data && groups.data.invites.length > 0 && (
        <Stack gap="xs">
          <Title order={4}>Invites for you</Title>
          {groups.data.invites.map((invite) => (
            <InviteCard key={invite.id} invite={invite} />
          ))}
        </Stack>
      )}

      {groups.data &&
        (groups.data.groups.length === 0 ? (
          <Text c="dimmed">
            You're not in any groups yet. Make one and invite people, or ask a friend to invite you.
          </Text>
        ) : (
          <Stack gap="xs">
            {groups.data.groups.map((group) => (
              <GroupCard key={group.id} group={group} />
            ))}
          </Stack>
        ))}
    </Stack>
  )
}
