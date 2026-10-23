import { Anchor, AppShell, Container, Group, Text, Title } from '@mantine/core'
import { Outlet } from 'react-router'

export function Layout() {
  return (
    <AppShell header={{ height: 56 }} footer={{ height: 40 }} padding="md">
      <AppShell.Header>
        <Container size="md" h="100%">
          <Group h="100%">
            <Title order={3}>Board Game Group</Title>
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
