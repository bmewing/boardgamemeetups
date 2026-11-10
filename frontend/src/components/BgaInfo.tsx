import { Anchor, Badge, Group, Text } from '@mantine/core'

import type { BgaLink } from '../api/bga'
import { bgaCounts } from './bgaCounts'

/** How a game plays on Board Game Arena: Premium or not, its player counts, and links. */
export function BgaInfo({
  bga,
  premiumHostGoing,
  showLobby = false,
}: {
  bga: BgaLink
  premiumHostGoing?: boolean
  showLobby?: boolean
}) {
  return (
    <Group gap="xs">
      {bga.premium && (
        <Badge
          size="xs"
          variant="light"
          color={premiumHostGoing === false ? 'orange' : 'grape'}
          tt="none"
          title="Only a Premium member can start a table; anyone can join it."
        >
          {premiumHostGoing === false ? 'Premium: nobody going has it' : 'Premium'}
        </Badge>
      )}
      {bga.status === 'beta' && (
        <Badge size="xs" variant="light" color="gray" tt="none">
          Beta on BGA
        </Badge>
      )}
      <Text size="xs" c="dimmed">
        {bgaCounts(bga.player_counts)} players on BGA
      </Text>
      <Anchor href={bga.game_url} target="_blank" rel="noreferrer" size="xs">
        Open on BGA
      </Anchor>
      {showLobby && (
        <Anchor href={bga.lobby_url} target="_blank" rel="noreferrer" size="xs">
          Start a table
        </Anchor>
      )}
    </Group>
  )
}
