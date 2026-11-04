import { useKindeAuth } from '@kinde-oss/kinde-auth-react'
import {
  Alert,
  Anchor,
  Avatar,
  Button,
  Card,
  Center,
  Group,
  Loader,
  Stack,
  Text,
  Title,
} from '@mantine/core'
import { useEffect } from 'react'
import { Link, useNavigate, useParams } from 'react-router'

import { useAcceptInvite, useInvite } from '../api/friends'
import { useMe } from '../api/me'
import { forgetInvite, rememberInvite } from '../auth/pendingInvite'

export function InvitePage() {
  const { token = '' } = useParams()
  const { isAuthenticated, isLoading, login, register } = useKindeAuth()
  const invite = useInvite(token)
  const me = useMe()
  const accept = useAcceptInvite()
  const navigate = useNavigate()

  // Back from signing in: this invite is on screen now, so stop holding on to it.
  useEffect(() => {
    if (isAuthenticated) forgetInvite()
  }, [isAuthenticated])

  if (invite.isPending || isLoading) {
    return (
      <Center py="xl">
        <Loader />
      </Center>
    )
  }
  if (invite.isError) return <Alert color="red">{invite.error.message}</Alert>
  if (invite.data === null) {
    return (
      <Stack align="center" py="xl">
        <Text>This invite link has expired or been turned off.</Text>
        <Text size="sm" c="dimmed">
          Ask whoever sent it for a new one.
        </Text>
      </Stack>
    )
  }

  const { inviter } = invite.data
  const signInFirst = (go: () => unknown) => () => {
    rememberInvite(token)
    go()
  }

  let action
  if (!isAuthenticated) {
    action = (
      <Stack gap="xs" align="center">
        <Button onClick={signInFirst(() => register())}>Create an account</Button>
        <Button variant="subtle" onClick={signInFirst(() => login())}>
          I already have an account
        </Button>
      </Stack>
    )
  } else if (me.data?.id === inviter.id) {
    action = (
      <Text size="sm" c="dimmed" ta="center">
        This is your own invite link. Send it to someone you'd like to play with.{' '}
        <Anchor component={Link} to="/friends">
          Back to Friends
        </Anchor>
      </Text>
    )
  } else {
    action = (
      <Stack gap="xs" align="center">
        <Button
          loading={accept.isPending}
          onClick={() =>
            accept.mutate(token, {
              onSuccess: (result) => navigate(`/people/${result.person.id}`, { replace: true }),
            })
          }
        >
          Become friends with {inviter.display_name}
        </Button>
        {accept.isError && (
          <Text size="sm" c="red">
            {accept.error.message}
          </Text>
        )}
      </Stack>
    )
  }

  return (
    <Center py="xl">
      <Card withBorder padding="xl" maw={420} w="100%">
        <Stack align="center" gap="md">
          <Group>
            <Avatar
              src={inviter.avatar_url}
              name={inviter.display_name}
              color="initials"
              radius="xl"
              size="lg"
            />
          </Group>
          <Title order={3} ta="center">
            {inviter.display_name} invited you to be friends
          </Title>
          <Text size="sm" c="dimmed" ta="center">
            Board Game Group helps friends plan game nights and pick what to play.
          </Text>
          {action}
        </Stack>
      </Card>
    </Center>
  )
}
