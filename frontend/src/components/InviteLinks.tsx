import { Alert, Button, CopyButton, Group, Stack, Text, TextInput } from '@mantine/core'

import {
  type InviteLink,
  inviteUrl,
  useCreateInviteLink,
  useInviteLinks,
  useTurnOffInviteLink,
} from '../api/friends'
import { plural } from './userGameFields'
import { UnlockHint } from './achievements/UnlockHint'

const dateFormat = new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric' })

function LinkRow({ link }: { link: InviteLink }) {
  const turnOff = useTurnOffInviteLink()
  const url = inviteUrl(link.token)
  return (
    <Stack gap={4}>
      <Group gap="xs" wrap="nowrap">
        <TextInput
          value={url}
          readOnly
          aria-label="Invite link"
          style={{ flex: 1 }}
          onFocus={(e) => e.currentTarget.select()}
        />
        <CopyButton value={url}>
          {({ copied, copy }) => (
            <Button variant={copied ? 'light' : 'filled'} onClick={copy}>
              {copied ? 'Copied' : 'Copy'}
            </Button>
          )}
        </CopyButton>
      </Group>
      <Group gap="xs">
        <Text size="xs" c="dimmed">
          {plural(link.use_count, 'friend')} joined · works until{' '}
          {dateFormat.format(new Date(link.expires_at))}
        </Text>
        <Button
          size="compact-xs"
          variant="subtle"
          color="red"
          loading={turnOff.isPending}
          onClick={() => turnOff.mutate(link.id)}
        >
          Turn off
        </Button>
      </Group>
    </Stack>
  )
}

/** Your open invite links, and a button to make one. */
export function InviteLinks() {
  const links = useInviteLinks()
  const create = useCreateInviteLink()

  return (
    <Stack gap="sm">
      <Text size="sm" c="dimmed">
        Anyone who opens a link becomes your friend as soon as they sign in, with no request to
        answer. Links work for 30 days; turn one off if it ends up somewhere it shouldn't.
      </Text>
      <UnlockHint achievement="recruit" text="someone new to the site signs up with your link" />
      {links.data?.map((link) => (
        <LinkRow key={link.id} link={link} />
      ))}
      {create.isError && <Alert color="red">{create.error.message}</Alert>}
      <Group>
        <Button variant="default" loading={create.isPending} onClick={() => create.mutate()}>
          Make an invite link
        </Button>
      </Group>
    </Stack>
  )
}
