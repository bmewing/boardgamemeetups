import { Button, Stack, Text } from '@mantine/core'

import {
  type Person,
  useBlocks,
  useFriendAction,
  useFriends,
  useSendFriendRequest,
} from '../api/friends'

/**
 * A friend request button for someone you've come across (in a group, say). Shows nothing
 * for yourself, your friends, people you've blocked, or until your friends have loaded.
 */
export function AddFriendButton({ person, meId }: { person: Person; meId: string }) {
  const friends = useFriends()
  const blocks = useBlocks()
  const send = useSendFriendRequest()
  const act = useFriendAction()

  if (!friends.data || !blocks.data || !meId || person.id === meId) return null
  const has = (list: { person: Person }[]) => list.some((f) => f.person.id === person.id)
  if (has(friends.data.friends) || blocks.data.some((b) => b.id === person.id)) return null

  const name = person.display_name
  if (has(friends.data.outgoing)) {
    return (
      <Text size="xs" c="dimmed">
        Request sent
      </Text>
    )
  }
  if (has(friends.data.incoming)) {
    return (
      <Button
        size="compact-xs"
        variant="light"
        loading={act.isPending}
        aria-label={`Accept ${name}'s friend request`}
        onClick={() => act.mutate({ userId: person.id, action: 'accept' })}
      >
        Accept request
      </Button>
    )
  }
  const error = send.error?.message ?? act.error?.message
  return (
    <Stack gap={2} align="flex-end">
      <Button
        size="compact-xs"
        variant="light"
        loading={send.isPending}
        aria-label={`Add ${name} as a friend`}
        onClick={() => send.mutate({ user_id: person.id })}
      >
        Add friend
      </Button>
      {error && (
        <Text size="xs" c="red">
          {error}
        </Text>
      )}
    </Stack>
  )
}
