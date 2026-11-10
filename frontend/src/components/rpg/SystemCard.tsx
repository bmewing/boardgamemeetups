import { Anchor, Badge, Card, Group, Image, Stack, Text } from '@mantine/core'
import type { ReactNode } from 'react'
import { Link } from 'react-router'

import type { RpgSystemSummary } from '../../api/rpg'

/** An RPG system in a list; `below` holds controls, so only the picture and name link. */
export function SystemCard({ system, below }: { system: RpgSystemSummary; below?: ReactNode }) {
  const href = `/rpg-systems/${system.id}`
  return (
    <Card withBorder padding="sm">
      <Stack gap="sm">
        <Group wrap="nowrap" align="center">
          <Link to={href} tabIndex={-1} aria-hidden style={{ flexShrink: 0 }}>
            <Image
              src={system.thumbnail_url}
              alt=""
              w={48}
              h={48}
              radius="sm"
              fit="contain"
              fallbackSrc="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg'/%3E"
              bg="var(--mantine-color-default-hover)"
            />
          </Link>
          <Group gap="xs" style={{ minWidth: 0 }}>
            <Anchor component={Link} to={href} c="inherit">
              <Text fw={600} lineClamp={2}>
                {system.name}
              </Text>
            </Anchor>
            {system.is_custom && (
              <Badge size="xs" variant="light" color="olive">
                Not on RPGGeek
              </Badge>
            )}
          </Group>
        </Group>
        {below}
      </Stack>
    </Card>
  )
}
