import { Anchor, Avatar, Group, Text } from '@mantine/core'
import type { ReactNode } from 'react'
import { Link } from 'react-router'

import type { Person } from '../api/friends'

/** Someone's avatar and name, linking to their page, with controls on the right. */
export function PersonRow({
  person,
  note,
  linked = true,
  children,
}: {
  person: Person
  note?: ReactNode
  /** False for someone whose page you can't open, such as a person you've blocked. */
  linked?: boolean
  children?: ReactNode
}) {
  return (
    <Group justify="space-between" wrap="nowrap" gap="sm">
      <Group gap="sm" wrap="nowrap" style={{ minWidth: 0 }}>
        <Avatar src={person.avatar_url} name={person.display_name} color="initials" radius="xl" />
        <div style={{ minWidth: 0 }}>
          {linked ? (
            <Anchor component={Link} to={`/people/${person.id}`} c="inherit" fw={500} lineClamp={1}>
              {person.display_name}
            </Anchor>
          ) : (
            <Text fw={500} lineClamp={1}>
              {person.display_name}
            </Text>
          )}
          {note && (
            <Text size="xs" c="dimmed">
              {note}
            </Text>
          )}
        </div>
      </Group>
      {children && (
        <Group gap="xs" wrap="nowrap">
          {children}
        </Group>
      )}
    </Group>
  )
}
