import {
  Alert,
  Button,
  Card,
  Center,
  Group,
  Loader,
  Menu,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { type FormEvent, type ReactNode, useState } from 'react'

import {
  FriendRequestError,
  useBlocks,
  useFriendAction,
  useFriends,
  useSendFriendRequest,
} from '../api/friends'
import { InviteLinks } from '../components/InviteLinks'
import { PersonRow } from '../components/PersonRow'

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Card withBorder padding="md">
      <Stack gap="sm">
        <Title order={4}>{title}</Title>
        {children}
      </Stack>
    </Card>
  )
}

function AddByEmail() {
  const [email, setEmail] = useState('')
  const send = useSendFriendRequest()

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (email.trim()) send.mutate(email.trim())
  }

  const result = send.data
  const notFound = send.error instanceof FriendRequestError && send.error.notFound
  return (
    <Stack gap="sm">
      <form onSubmit={submit}>
        <Group align="flex-end" gap="xs" wrap="nowrap">
          <TextInput
            label="Their email address"
            description="The exact address they sign in with."
            type="email"
            value={email}
            onChange={(e) => {
              setEmail(e.currentTarget.value)
              send.reset()
            }}
            style={{ flex: 1 }}
          />
          <Button type="submit" loading={send.isPending}>
            Send request
          </Button>
        </Group>
      </form>
      {result && (
        <Alert color="green">
          {result.relation === 'friends'
            ? `You and ${result.person.display_name} are now friends.`
            : `Request sent to ${result.person.display_name}.`}
        </Alert>
      )}
      {notFound && (
        <Alert color="blue" title="No one here uses that email yet">
          Make an invite link below and send it to them. They'll become your friend when they sign
          up.
        </Alert>
      )}
      {send.isError && !notFound && <Alert color="red">{send.error.message}</Alert>}
    </Stack>
  )
}

export function FriendsPage() {
  const friends = useFriends()
  const blocks = useBlocks()
  const act = useFriendAction()

  const busy = (userId: string) => act.isPending && act.variables?.userId === userId

  return (
    <Stack>
      <Title order={2}>Friends</Title>
      <Section title="Add a friend">
        <AddByEmail />
      </Section>

      {friends.isPending && (
        <Center py="xl">
          <Loader />
        </Center>
      )}
      {friends.isError && <Alert color="red">{friends.error.message}</Alert>}
      {act.isError && <Alert color="red">{act.error.message}</Alert>}

      {friends.data && friends.data.incoming.length > 0 && (
        <Section title="Asking to be your friend">
          {friends.data.incoming.map(({ person }) => (
            <PersonRow key={person.id} person={person}>
              <Button
                size="xs"
                loading={busy(person.id)}
                onClick={() => act.mutate({ userId: person.id, action: 'accept' })}
              >
                Accept
              </Button>
              <Menu position="bottom-end" withinPortal>
                <Menu.Target>
                  <Button size="xs" variant="default" disabled={busy(person.id)}>
                    Decline
                  </Button>
                </Menu.Target>
                <Menu.Dropdown>
                  <Menu.Item onClick={() => act.mutate({ userId: person.id, action: 'decline' })}>
                    Decline
                  </Menu.Item>
                  <Menu.Item
                    color="red"
                    onClick={() => act.mutate({ userId: person.id, action: 'block' })}
                  >
                    Decline and block
                  </Menu.Item>
                </Menu.Dropdown>
              </Menu>
            </PersonRow>
          ))}
        </Section>
      )}

      {friends.data && (
        <Section title="Your friends">
          {friends.data.friends.length === 0 ? (
            <Text c="dimmed" size="sm">
              No friends yet. Add someone by email, or send them an invite link.
            </Text>
          ) : (
            friends.data.friends.map(({ person }) => <PersonRow key={person.id} person={person} />)
          )}
        </Section>
      )}

      {friends.data && friends.data.outgoing.length > 0 && (
        <Section title="Waiting for an answer">
          {friends.data.outgoing.map(({ person }) => (
            <PersonRow key={person.id} person={person}>
              <Button
                size="xs"
                variant="default"
                loading={busy(person.id)}
                onClick={() => act.mutate({ userId: person.id, action: 'remove' })}
              >
                Cancel
              </Button>
            </PersonRow>
          ))}
        </Section>
      )}

      <Section title="Invite links">
        <InviteLinks />
      </Section>

      {blocks.data && blocks.data.length > 0 && (
        <Section title="Blocked">
          <Text size="sm" c="dimmed">
            They can't find you by email, ask to be friends, or use your invite links.
          </Text>
          {blocks.data.map((person) => (
            <PersonRow key={person.id} person={person} linked={false}>
              <Button
                size="xs"
                variant="default"
                loading={busy(person.id)}
                onClick={() => act.mutate({ userId: person.id, action: 'unblock' })}
              >
                Unblock
              </Button>
            </PersonRow>
          ))}
        </Section>
      )}
    </Stack>
  )
}
