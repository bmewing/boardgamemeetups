import { useKindeAuth } from '@kinde-oss/kinde-auth-react'
import { Alert, Button, Card, Stack, Text, Title } from '@mantine/core'
import { useEffect } from 'react'
import { useParams } from 'react-router'

import { useDiscordLink, useLinkDiscord } from '../api/discord'
import { useMe } from '../api/me'
import { forgetDiscordLink, rememberDiscordLink } from '../auth/pendingInvite'
import { LoadingNote, MascotNote } from '../components/mascot/MascotNote'

/** Where the Discord bot's "Link my account" button lands. Linking asks for a click, since
 * link previews open links too. */
export function DiscordLinkPage() {
  const { token = '' } = useParams()
  const { isAuthenticated, isLoading, login, register } = useKindeAuth()
  const link = useDiscordLink(token)
  const me = useMe()
  const save = useLinkDiscord()

  // Back from signing in: this link is on screen now, so stop holding on to it.
  useEffect(() => {
    if (isAuthenticated) forgetDiscordLink()
  }, [isAuthenticated])

  if (link.isPending || isLoading) {
    return <LoadingNote>Opening your link…</LoadingNote>
  }
  if (link.isError) {
    return (
      <MascotNote pose="snooze">
        <Text>This link has expired.</Text>
        <Text size="sm" c="dimmed">
          Type <code>/bggroup link</code> in Discord for a new one.
        </Text>
      </MascotNote>
    )
  }

  const discordName = link.data.discord_username
  if (save.isSuccess) {
    return (
      <MascotNote pose="cheer">
        <Text>Linked! Discord's @{discordName} is you.</Text>
        <Text size="sm" c="dimmed">
          Head back to Discord. The buttons on the bot's posts work for you now.
        </Text>
      </MascotNote>
    )
  }

  const signInFirst = (go: () => unknown) => () => {
    rememberDiscordLink(token)
    go()
  }

  return (
    <Stack maw={520}>
      <Title order={2}>Link Discord</Title>
      <Card withBorder>
        <Stack>
          <Text>
            Link Discord's <b>@{discordName}</b> to your Board Game Group account, so you can say
            whether you're coming from Discord.
          </Text>
          {isAuthenticated ? (
            <>
              {me.data && (
                <Text size="sm" c="dimmed">
                  Signed in as {me.data.display_name}
                  {me.data.discord_username && me.data.discord_username !== discordName
                    ? `, linked to @${me.data.discord_username} now. Linking replaces it.`
                    : '.'}
                </Text>
              )}
              <Button loading={save.isPending} onClick={() => save.mutate(token)}>
                Link my account
              </Button>
              {save.isError && <Alert color="red">{save.error.message}</Alert>}
            </>
          ) : (
            <Stack gap="xs" align="flex-start">
              <Button onClick={signInFirst(() => login())}>Sign in to link</Button>
              <Button variant="subtle" onClick={signInFirst(() => register())}>
                I don't have an account yet
              </Button>
            </Stack>
          )}
        </Stack>
      </Card>
    </Stack>
  )
}
