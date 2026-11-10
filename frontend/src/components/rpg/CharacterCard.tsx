import { Avatar, Badge, Card, Group, Stack, Text } from '@mantine/core'
import type { ReactNode } from 'react'
import { Link } from 'react-router'

import { type Character, STATUS_LABELS } from '../../api/rpg'
import { characterLine } from './characterLine'

const STATUS_COLORS = { active: 'teal', retired: 'gray', dead: 'red' } as const

/** A character in a list. `showOwner` names whose it is, for party lists. */
export function CharacterCard({
  character,
  showOwner,
  showSystem = true,
  children,
}: {
  character: Character
  showOwner?: boolean
  showSystem?: boolean
  children?: ReactNode
}) {
  const line = characterLine(character)
  return (
    <Card component={Link} to={`/characters/${character.id}`} withBorder padding="sm">
      <Group wrap="nowrap" align="flex-start">
        <Avatar src={character.portrait_url} alt="" size={56} radius="sm">
          {character.name.slice(0, 1).toUpperCase()}
        </Avatar>
        <Stack gap={2} style={{ minWidth: 0 }}>
          <Group gap="xs">
            <Text fw={600} lineClamp={1}>
              {character.name}
            </Text>
            {character.pronouns && (
              <Text span size="sm" c="dimmed">
                ({character.pronouns})
              </Text>
            )}
            {character.status !== 'active' && (
              <Badge size="xs" variant="light" color={STATUS_COLORS[character.status]}>
                {STATUS_LABELS[character.status]}
              </Badge>
            )}
          </Group>
          {line && <Text size="sm">{line}</Text>}
          <Text size="sm" c="dimmed">
            {[
              showSystem ? character.system.name : null,
              showOwner ? `played by ${character.owner.display_name}` : null,
            ]
              .filter(Boolean)
              .join(' · ')}
          </Text>
          {children}
        </Stack>
      </Group>
    </Card>
  )
}
