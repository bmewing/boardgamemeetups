import {
  ActionIcon,
  Alert,
  Badge,
  Box,
  Button,
  Card,
  Center,
  Group,
  Loader,
  Menu,
  Modal,
  Pagination,
  SegmentedControl,
  SimpleGrid,
  Stack,
  Table,
  Text,
  Textarea,
  TextInput,
  Title,
  Tooltip,
} from '@mantine/core'
import { useDebouncedValue } from '@mantine/hooks'
import { type ReactNode, useState } from 'react'

import {
  ADMIN_PAGE_SIZE,
  type AdminStats,
  type AdminUser,
  type AdminUserFilter,
  useAdminStats,
  useAdminUsers,
  useBanUser,
  useDeleteUser,
  useUnbanUser,
} from '../api/admin'
import { useMe } from '../api/me'
import { plural } from '../components/userGameFields'
import { PlayerPiece } from '../components/pieces/PlayerPiece'

const count = new Intl.NumberFormat()
const day = new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
const weekLabel = new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric' })
const relative = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' })

/** "3 hours ago", "yesterday", or a date once it's more than a month back. */
function ago(iso: string | null, now = Date.now()): string {
  if (!iso) return 'Never'
  const minutes = Math.round((new Date(iso).getTime() - now) / 60_000)
  if (minutes > -5) return 'Just now'
  if (minutes > -60) return relative.format(minutes, 'minute')
  if (minutes > -60 * 24) return relative.format(Math.round(minutes / 60), 'hour')
  if (minutes > -60 * 24 * 30) return relative.format(Math.round(minutes / 60 / 24), 'day')
  return day.format(new Date(iso))
}

/** A Monday from the API (YYYY-MM-DD), as a local calendar date. */
function weekOf(isoDate: string) {
  const [y, m, d] = isoDate.split('-').map(Number)
  return new Date(y, m - 1, d)
}

function StatTile({ label, value, note }: { label: string; value: number; note?: ReactNode }) {
  return (
    <Card withBorder padding="md">
      <Text size="sm" c="dimmed">
        {label}
      </Text>
      <Text fz={28} fw={700} lh={1.2}>
        {count.format(value)}
      </Text>
      {note && (
        <Text size="xs" c="dimmed">
          {note}
        </Text>
      )}
    </Card>
  )
}

const CHART_HEIGHT = 120

/** One column per week; hover a column for its count. */
function SignupChart({ weeks }: { weeks: AdminStats['signups_by_week'] }) {
  const peak = Math.max(1, ...weeks.map((week) => week.count))
  const total = weeks.reduce((sum, week) => sum + week.count, 0)
  const described = weeks
    .map((week) => `${weekLabel.format(weekOf(week.week_start))}: ${week.count}`)
    .join(', ')
  return (
    <Card withBorder padding="md">
      <Group justify="space-between" align="baseline" mb="sm">
        <Text fw={600}>Sign-ups by week</Text>
        <Text size="sm" c="dimmed">
          {plural(total, 'sign-up')} in {weeks.length} weeks
        </Text>
      </Group>
      <Group
        gap={2}
        align="flex-end"
        wrap="nowrap"
        h={CHART_HEIGHT}
        role="img"
        aria-label={`Sign-ups by week: ${described}`}
        style={{ borderBottom: '1px solid var(--mantine-color-default-border)' }}
      >
        {weeks.map((week) => (
          <Tooltip
            key={week.week_start}
            label={`Week of ${weekLabel.format(weekOf(week.week_start))}: ${plural(week.count, 'sign-up')}`}
            withinPortal
          >
            {/* The whole column is the hover target, not just the bar. */}
            <Box h="100%" style={{ flex: 1, display: 'flex', alignItems: 'flex-end' }}>
              <Box
                w="100%"
                h={week.count ? Math.max(3, (week.count / peak) * CHART_HEIGHT) : 0}
                bg="var(--mantine-primary-color-filled)"
                style={{ borderRadius: '4px 4px 0 0' }}
              />
            </Box>
          </Tooltip>
        ))}
      </Group>
      <Group justify="space-between" mt={4}>
        <Text size="xs" c="dimmed">
          {weeks.length > 0 && weekLabel.format(weekOf(weeks[0].week_start))}
        </Text>
        <Text size="xs" c="dimmed">
          This week
        </Text>
      </Group>
    </Card>
  )
}

function Stats() {
  const stats = useAdminStats()
  if (stats.isPending) {
    return (
      <Center py="xl">
        <Loader />
      </Center>
    )
  }
  if (stats.isError) return <Alert color="red">{stats.error.message}</Alert>
  const { users, activity, signups_by_week } = stats.data
  return (
    <Stack gap="sm">
      <SimpleGrid cols={{ base: 2, sm: 4 }} spacing="sm">
        <StatTile label="Users" value={users.total} note={`${users.new_7d} new this week`} />
        <StatTile
          label="Active this week"
          value={users.active_7d}
          note={`${users.active_30d} in the last 30 days`}
        />
        <StatTile label="New in 30 days" value={users.new_30d} />
        <StatTile label="Banned" value={users.banned} note={plural(users.admins, 'admin')} />
      </SimpleGrid>
      <SignupChart weeks={signups_by_week} />
      <SimpleGrid cols={{ base: 2, sm: 3 }} spacing="sm">
        <StatTile label="Groups" value={activity.groups} />
        <StatTile
          label="Upcoming dates"
          value={activity.meetups_upcoming}
          note={`${count.format(activity.meetups_past)} held so far`}
        />
        <StatTile label="Plays logged" value={activity.plays_logged} />
        <StatTile label="Games owned" value={activity.games_owned} note="across all collections" />
        <StatTile label="Friendships" value={activity.friendships} />
        <StatTile label="Games in catalog" value={activity.catalog_games} />
      </SimpleGrid>
    </Stack>
  )
}

function BanModal({ user, onClose }: { user: AdminUser; onClose: () => void }) {
  const ban = useBanUser()
  const [reason, setReason] = useState(user.ban_reason ?? '')
  return (
    <Modal opened onClose={onClose} title={`Ban ${user.display_name}?`}>
      <Stack>
        <Text size="sm">
          They'll be signed out of everything and can't use the app until the ban is lifted. Their
          games, groups and friends stay as they are.
        </Text>
        <Textarea
          label="Reason"
          description="For other admins; they don't see it."
          maxLength={500}
          autosize
          minRows={2}
          value={reason}
          onChange={(e) => setReason(e.currentTarget.value)}
          data-autofocus
        />
        {ban.isError && <Alert color="red">{ban.error.message}</Alert>}
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            Cancel
          </Button>
          <Button
            color="red"
            loading={ban.isPending}
            onClick={() => ban.mutate({ userId: user.id, reason }, { onSuccess: onClose })}
          >
            Ban
          </Button>
        </Group>
      </Stack>
    </Modal>
  )
}

function DeleteModal({ user, onClose }: { user: AdminUser; onClose: () => void }) {
  const remove = useDeleteUser()
  return (
    <Modal opened onClose={onClose} title={`Delete ${user.display_name}?`}>
      <Stack>
        <Text size="sm">
          This deletes their account and everything in it: their games, answers, friends and votes.
          Groups they own pass to another member. It can't be undone.
        </Text>
        <Text size="sm" c="dimmed">
          They can still sign in again and start a fresh account. To keep them out, ban them
          instead.
        </Text>
        {remove.isError && <Alert color="red">{remove.error.message}</Alert>}
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            Cancel
          </Button>
          <Button
            color="red"
            loading={remove.isPending}
            onClick={() => remove.mutate(user.id, { onSuccess: onClose })}
          >
            Delete account
          </Button>
        </Group>
      </Stack>
    </Modal>
  )
}

type Pending = { kind: 'ban' | 'delete'; user: AdminUser } | null

function UserActions({
  user,
  isMe,
  onPick,
}: {
  user: AdminUser
  isMe: boolean
  onPick: (pending: Pending) => void
}) {
  const unban = useUnbanUser()
  if (isMe) {
    return (
      <Text size="xs" c="dimmed">
        You
      </Text>
    )
  }
  const banned = user.banned_at !== null
  return (
    <Menu position="bottom-end" withinPortal>
      <Menu.Target>
        <ActionIcon
          variant="subtle"
          color="gray"
          aria-label={`Actions for ${user.display_name}`}
          loading={unban.isPending}
        >
          ⋯
        </ActionIcon>
      </Menu.Target>
      <Menu.Dropdown>
        {banned ? (
          <Menu.Item onClick={() => unban.mutate(user.id)}>Lift ban</Menu.Item>
        ) : (
          <Menu.Item
            color="red"
            disabled={user.is_admin}
            onClick={() => onPick({ kind: 'ban', user })}
          >
            Ban…
          </Menu.Item>
        )}
        <Menu.Item
          color="red"
          disabled={user.is_admin}
          onClick={() => onPick({ kind: 'delete', user })}
        >
          Delete account…
        </Menu.Item>
        {user.is_admin && <Menu.Label>Take away their admin role in Kinde first</Menu.Label>}
      </Menu.Dropdown>
    </Menu>
  )
}

function Users() {
  const me = useMe()
  const [search, setSearch] = useState('')
  const [q] = useDebouncedValue(search.trim(), 300)
  const [show, setShow] = useState<AdminUserFilter>('all')
  const [page, setPage] = useState(0)
  const [pending, setPending] = useState<Pending>(null)
  const users = useAdminUsers(q, show, page)
  const pages = Math.ceil((users.data?.total ?? 0) / ADMIN_PAGE_SIZE)

  return (
    <Stack gap="sm">
      <Group justify="space-between" align="flex-end">
        <Title order={3}>Users</Title>
        {users.data && (
          <Text size="sm" c="dimmed">
            {plural(users.data.total, 'match', 'matches')}
          </Text>
        )}
      </Group>
      <Group gap="sm" wrap="wrap">
        <TextInput
          placeholder="Search names and emails"
          aria-label="Search users"
          value={search}
          onChange={(e) => {
            setSearch(e.currentTarget.value)
            setPage(0)
          }}
          style={{ flex: 1, minWidth: 200 }}
        />
        <SegmentedControl
          value={show}
          onChange={(value) => {
            setShow(value as AdminUserFilter)
            setPage(0)
          }}
          data={[
            { value: 'all', label: 'All' },
            { value: 'banned', label: 'Banned' },
            { value: 'admins', label: 'Admins' },
          ]}
        />
      </Group>

      {users.isPending && (
        <Center py="xl">
          <Loader />
        </Center>
      )}
      {users.isError && <Alert color="red">{users.error.message}</Alert>}
      {users.data &&
        (users.data.users.length === 0 ? (
          <Text c="dimmed">Nobody matches.</Text>
        ) : (
          <Table.ScrollContainer minWidth={720}>
            <Table verticalSpacing="xs" highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Person</Table.Th>
                  <Table.Th>Joined</Table.Th>
                  <Table.Th>Last seen</Table.Th>
                  <Table.Th ta="right">Games</Table.Th>
                  <Table.Th ta="right">Groups</Table.Th>
                  <Table.Th />
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {users.data.users.map((user) => (
                  <Table.Tr key={user.id}>
                    <Table.Td>
                      <Group gap="sm" wrap="nowrap">
                        <PlayerPiece person={user} size={26} label="" />
                        <div>
                          <Group gap={6} wrap="nowrap">
                            <Text size="sm" fw={500}>
                              {user.display_name}
                            </Text>
                            {user.is_admin && (
                              <Badge size="xs" variant="light">
                                Admin
                              </Badge>
                            )}
                            {user.banned_at && (
                              <Tooltip
                                label={`Banned ${day.format(new Date(user.banned_at))}${user.ban_reason ? `: ${user.ban_reason}` : ''}`}
                                multiline
                                maw={300}
                                withinPortal
                              >
                                <Badge size="xs" color="red" variant="light">
                                  Banned
                                </Badge>
                              </Tooltip>
                            )}
                          </Group>
                          <Text size="xs" c="dimmed">
                            {user.email ?? 'No email'}
                          </Text>
                        </div>
                      </Group>
                    </Table.Td>
                    <Table.Td>
                      <Text size="sm">{day.format(new Date(user.created_at))}</Text>
                    </Table.Td>
                    <Table.Td>
                      <Text size="sm">{ago(user.last_seen_at)}</Text>
                    </Table.Td>
                    <Table.Td ta="right">
                      <Text size="sm">{count.format(user.games_owned)}</Text>
                    </Table.Td>
                    <Table.Td ta="right">
                      <Text size="sm">{count.format(user.groups)}</Text>
                    </Table.Td>
                    <Table.Td ta="right">
                      <UserActions user={user} isMe={user.id === me.data?.id} onPick={setPending} />
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
        ))}
      {pages > 1 && (
        <Center>
          <Pagination total={pages} value={page + 1} onChange={(value) => setPage(value - 1)} />
        </Center>
      )}

      {pending?.kind === 'ban' && <BanModal user={pending.user} onClose={() => setPending(null)} />}
      {pending?.kind === 'delete' && (
        <DeleteModal user={pending.user} onClose={() => setPending(null)} />
      )}
    </Stack>
  )
}

export function AdminPage() {
  const me = useMe()
  if (me.isPending) {
    return (
      <Center py="xl">
        <Loader />
      </Center>
    )
  }
  if (!me.data?.is_admin) return <Text py="xl">Only admins can see this page.</Text>
  return (
    <Stack gap="xl">
      <Title order={2}>Admin</Title>
      <Stats />
      <Users />
    </Stack>
  )
}
