import {
  ActionIcon,
  Alert,
  Anchor,
  Avatar,
  Badge,
  Button,
  Center,
  Group,
  Loader,
  Menu,
  SegmentedControl,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'

import {
  type PersonProfile,
  type SharedGame,
  useFriendAction,
  usePerson,
  usePersonGames,
} from '../api/friends'
import { GameCard } from '../components/GameCard'
import {
  isOwned,
  isWanted,
  OWNERSHIP_LABELS,
  plural,
  teaches,
  WISHLIST_LABELS,
} from '../components/userGameFields'

type Shelf = 'owned' | 'wanted' | 'all'

function TheirAnswers({ row }: { row: SharedGame }) {
  const badges = [
    row.ownership && OWNERSHIP_LABELS[row.ownership],
    row.wishlist_priority !== null && `Wishlist: ${WISHLIST_LABELS[row.wishlist_priority]}`,
    row.want_to_play && 'Wants to play',
    row.rating !== null && `Rated ${row.rating}`,
    teaches(row) && `Can teach${row.teach_minutes ? ` (${row.teach_minutes} min)` : ''}`,
    row.plays > 0 && plural(row.plays, 'play'),
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

function TheirGames({ profile }: { profile: PersonProfile }) {
  const games = usePersonGames(profile.person.id, profile.games_visible)
  const [shelf, setShelf] = useState<Shelf>('owned')
  const [name, setName] = useState('')

  const shown = useMemo(() => {
    const q = name.trim().toLowerCase()
    return (games.data ?? []).filter(
      (row) =>
        (shelf === 'all' || (shelf === 'owned' ? isOwned(row) : isWanted(row))) &&
        (!q || row.game.name.toLowerCase().includes(q)),
    )
  }, [games.data, shelf, name])

  if (!profile.games_visible) {
    return <Text c="dimmed">{profile.person.display_name} doesn't share their games with you.</Text>
  }
  if (games.isPending) {
    return (
      <Center py="xl">
        <Loader />
      </Center>
    )
  }
  if (games.isError) return <Alert color="red">{games.error.message}</Alert>
  if (games.data.length === 0) {
    return <Text c="dimmed">{profile.person.display_name} hasn't added any games yet.</Text>
  }
  return (
    <Stack>
      <SegmentedControl
        value={shelf}
        onChange={(value) => setShelf(value as Shelf)}
        data={[
          { value: 'owned', label: 'Owned' },
          { value: 'wanted', label: 'Wishlist & want to play' },
          { value: 'all', label: 'All' },
        ]}
      />
      <TextInput label="Name" value={name} onChange={(e) => setName(e.currentTarget.value)} />
      <Text size="sm" c="dimmed">
        {shown.length} of {plural(games.data.length, 'game')}
      </Text>
      {shown.length === 0 && <Text c="dimmed">No games match.</Text>}
      <Stack gap="xs">
        {shown.map((row) => (
          <GameCard key={row.game.id} game={row.game}>
            <TheirAnswers row={row} />
          </GameCard>
        ))}
      </Stack>
    </Stack>
  )
}

function Standing({ profile }: { profile: PersonProfile }) {
  const act = useFriendAction()
  const navigate = useNavigate()
  const { person, relation } = profile
  const run = (action: 'accept' | 'decline' | 'remove') => act.mutate({ userId: person.id, action })

  const block = () =>
    act.mutate(
      { userId: person.id, action: 'block' },
      { onSuccess: () => navigate('/friends', { replace: true }) },
    )

  return (
    <Stack gap="xs" align="flex-end">
      <Group gap="xs">
        {relation === 'friends' && <Badge variant="light">Friends</Badge>}
        {relation === 'incoming' && (
          <>
            <Button size="xs" loading={act.isPending} onClick={() => run('accept')}>
              Accept request
            </Button>
            <Button size="xs" variant="default" onClick={() => run('decline')}>
              Decline
            </Button>
          </>
        )}
        {relation === 'outgoing' && (
          <>
            <Badge variant="light" color="gray">
              Request sent
            </Badge>
            <Button size="xs" variant="default" onClick={() => run('remove')}>
              Cancel request
            </Button>
          </>
        )}
        {relation !== 'self' && (
          <Menu position="bottom-end" withinPortal>
            <Menu.Target>
              <ActionIcon variant="subtle" color="gray" aria-label="More">
                ⋯
              </ActionIcon>
            </Menu.Target>
            <Menu.Dropdown>
              {relation === 'friends' && (
                <Menu.Item onClick={() => run('remove')}>Remove friend</Menu.Item>
              )}
              <Menu.Item color="red" onClick={block}>
                Block {person.display_name}
              </Menu.Item>
            </Menu.Dropdown>
          </Menu>
        )}
      </Group>
      {act.isError && (
        <Text size="sm" c="red">
          {act.error.message}
        </Text>
      )}
    </Stack>
  )
}

export function PersonPage() {
  const { userId = '' } = useParams()
  const profile = usePerson(userId)

  if (profile.isPending) {
    return (
      <Center py="xl">
        <Loader />
      </Center>
    )
  }
  if (profile.isError) return <Alert color="red">{profile.error.message}</Alert>
  if (profile.data === null) {
    return (
      <Stack>
        <Text>We couldn't find this person.</Text>
        <Anchor component={Link} to="/friends">
          Back to Friends
        </Anchor>
      </Stack>
    )
  }

  const { person, relation } = profile.data
  return (
    <Stack>
      <Group justify="space-between" align="flex-start">
        <Group gap="md" wrap="nowrap">
          <Avatar
            src={person.avatar_url}
            name={person.display_name}
            color="initials"
            radius="xl"
            size="lg"
          />
          <div>
            <Title order={2}>{person.display_name}</Title>
            {relation === 'self' && (
              <Text size="sm" c="dimmed">
                This is how others see your games.{' '}
                <Anchor component={Link} to="/collection">
                  Edit them in My games
                </Anchor>
              </Text>
            )}
          </div>
        </Group>
        <Standing profile={profile.data} />
      </Group>
      <Title order={3}>Games</Title>
      <TheirGames profile={profile.data} />
    </Stack>
  )
}
