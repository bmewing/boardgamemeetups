import { Anchor, AppShell, Container, Group, Text, Title } from '@mantine/core'
import { Link, Outlet } from 'react-router'

import { UserMenu } from './UserMenu'

export function Layout() {
  return (
    <AppShell header={{ height: 56 }} footer={{ height: 40 }} padding="md">
      <AppShell.Header>
        <Container size="md" h="100%">
          <Group h="100%" justify="space-between">
            <Anchor component={Link} to="/" underline="never" c="inherit">
              <Title order={3}>Board Game Group</Title>
            </Anchor>
            <UserMenu />
          </Group>
        </Container>
      </AppShell.Header>
      <AppShell.Main>
        <Container size="md">
          <Outlet />
        </Container>
      </AppShell.Main>
      <AppShell.Footer>
        <Container size="md" h="100%">
          <Group h="100%" justify="center">
            <Text size="xs" c="dimmed">
              Game data powered by{' '}
              <Anchor href="https://boardgamegeek.com" target="_blank" size="xs">
                BoardGameGeek
              </Anchor>
            </Text>
          </Group>
        </Container>
      </AppShell.Footer>
    </AppShell>
  )
}
