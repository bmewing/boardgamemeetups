import { useKindeAuth } from '@kinde-oss/kinde-auth-react'
import { Anchor, Button, Card, Center, Group, Stack, Text, Title } from '@mantine/core'
import { useEffect } from 'react'
import { Link, useNavigate, useParams } from 'react-router'

import { useAcceptInvite, useInvite } from '../api/friends'
import { useMe } from '../api/me'
import { forgetInvite, rememberInvite } from '../auth/pendingInvite'
import { Grouper } from '../components/mascot/Grouper'
import { ErrorNote, LoadingNote, MascotNote } from '../components/mascot/MascotNote'
import { PlayerPiece } from '../components/pieces/PlayerPiece'

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
    return <LoadingNote>Opening your invite…</LoadingNote>
  }
  if (invite.isError) return <ErrorNote error={invite.error} onRetry={invite.refetch} />
  if (invite.data === null) {
    return (
      <MascotNote pose="snooze">
        <Text>This invite link has expired or been turned off.</Text>
        <Text size="sm" c="dimmed">
          Ask whoever sent it for a new one.
        </Text>
      </MascotNote>
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
          <Group gap={0} align="flex-end">
            <Grouper pose="wave" size={120} label="" />
            <PlayerPiece person={inviter} size={56} label="" />
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
