import { ActionIcon, Button, Group, Popover, Stack, Text } from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'

import { useRemoveMyGame } from '../api/collection'

function TrashIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M4 7h16M10 11v6M14 11v6M5 7l1 12a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2l1-12M9 7V4h6v3" />
    </svg>
  )
}

/** A trash button that asks once before removing a game and everything recorded about it. */
export function RemoveGameButton({
  gameId,
  name,
  overImage = false,
}: {
  gameId: number
  name: string
  /** Give the button a solid backdrop so it shows over box art. */
  overImage?: boolean
}) {
  const [opened, { close, toggle }] = useDisclosure(false)
  const remove = useRemoveMyGame()

  return (
    <Popover opened={opened} onChange={(open) => !open && close()} position="bottom-end" withArrow>
      <Popover.Target>
        <ActionIcon
          variant={overImage ? 'default' : 'subtle'}
          color="gray"
          aria-label={`Remove ${name}`}
          onClick={toggle}
          loading={remove.isPending}
        >
          <TrashIcon />
        </ActionIcon>
      </Popover.Target>
      <Popover.Dropdown maw={280}>
        <Stack gap="xs">
          <Text size="sm">
            Remove <b>{name}</b> from your games? Anything you recorded about it goes too.
          </Text>
          {remove.isError && (
            <Text size="sm" c="red">
              {remove.error.message}
            </Text>
          )}
          <Group gap="xs" justify="flex-end">
            <Button size="xs" variant="default" onClick={close}>
              Cancel
            </Button>
            <Button
              size="xs"
              color="red"
              loading={remove.isPending}
              onClick={() => remove.mutate(gameId, { onSuccess: close })}
            >
              Remove
            </Button>
          </Group>
        </Stack>
      </Popover.Dropdown>
    </Popover>
  )
}
