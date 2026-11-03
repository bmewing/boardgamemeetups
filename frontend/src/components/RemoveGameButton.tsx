import { ActionIcon, Button, Checkbox, Group, Popover, Stack, Text } from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { useState } from 'react'

import { useRemoveMyGame } from '../api/collection'
import type { GameSummary } from '../api/games'

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

interface Props {
  game: GameSummary
  /** Its expansions in the user's list, offered for removal along with it. */
  expansions?: GameSummary[]
  /** An icon for lists and tiles, or a labelled button for the game's own page. */
  variant?: 'icon' | 'text'
  /** Give the icon a solid backdrop so it shows over box art. */
  overImage?: boolean
  onRemoved?: () => void
}

/** Asks once before removing a game (and, if ticked, its expansions) from the user's list. */
export function RemoveGameButton({
  game,
  expansions = [],
  variant = 'icon',
  overImage = false,
  onRemoved,
}: Props) {
  const [opened, { open, close }] = useDisclosure(false)
  const [withExpansions, setWithExpansions] = useState(true)
  const remove = useRemoveMyGame()
  const toggle = () => {
    if (opened) return close()
    setWithExpansions(true)
    open()
  }
  const confirm = () =>
    remove.mutate(
      { gameId: game.id, expansionIds: withExpansions ? expansions.map((e) => e.id) : [] },
      {
        onSuccess: () => {
          close()
          onRemoved?.()
        },
      },
    )

  return (
    <Popover opened={opened} onChange={(o) => !o && close()} position="bottom-end" withArrow>
      <Popover.Target>
        {variant === 'icon' ? (
          <ActionIcon
            variant={overImage ? 'default' : 'subtle'}
            color="gray"
            aria-label={`Remove ${game.name}`}
            onClick={toggle}
            loading={remove.isPending}
          >
            <TrashIcon />
          </ActionIcon>
        ) : (
          <Button size="xs" variant="subtle" color="red" onClick={toggle}>
            Remove from my games
          </Button>
        )}
      </Popover.Target>
      <Popover.Dropdown maw={300}>
        <Stack gap="xs">
          <Text size="sm">
            Remove <b>{game.name}</b> from your games? Anything you recorded about it goes too.
          </Text>
          {expansions.length > 0 && (
            <Checkbox
              size="xs"
              checked={withExpansions}
              onChange={(e) => setWithExpansions(e.currentTarget.checked)}
              label={
                expansions.length === 1
                  ? 'Also remove its expansion'
                  : `Also remove its ${expansions.length} expansions`
              }
              description={expansions.map((e) => e.name).join(', ')}
            />
          )}
          {remove.isError && (
            <Text size="sm" c="red">
              {remove.error.message}
            </Text>
          )}
          <Group gap="xs" justify="flex-end">
            <Button size="xs" variant="default" onClick={close}>
              Cancel
            </Button>
            <Button size="xs" color="red" loading={remove.isPending} onClick={confirm}>
              Remove
            </Button>
          </Group>
        </Stack>
      </Popover.Dropdown>
    </Popover>
  )
}
