import { useKindeAuth } from '@kinde-oss/kinde-auth-react'
import {
  Alert,
  Anchor,
  AppShell,
  Button,
  Container,
  Group,
  Image,
  Indicator,
  Stack,
  Title,
} from '@mantine/core'
import { Link, NavLink, Outlet } from 'react-router'

import { useGroups } from '../api/groups'
import { AccountSuspendedError, useMe } from '../api/me'
import { useResumeInvite } from '../auth/pendingInvite'
import { UserMenu } from './UserMenu'

function PoweredByBgg() {
  // Required by BGG's API terms: their logo, legible, linking back to BoardGameGeek.
  // The logo's dark text needs a light backdrop in dark mode.
  return (
    <Anchor
      href="https://boardgamegeek.com"
      target="_blank"
      bg="white"
      px={6}
      py={2}
      style={{ borderRadius: 4, lineHeight: 0 }}
    >
      <Image src="/powered-by-bgg.png" alt="Powered by BGG" h={24} w="auto" />
    </Anchor>
  )
}

/** Groups, with a dot when an invite is waiting for an answer. */
function GroupsLink() {
  const groups = useGroups()
  const waiting = groups.data?.invites.length ?? 0
  return (
    <Indicator disabled={waiting === 0} color="red" size={8} offset={-2}>
      <Anchor
        component={NavLink}
        to="/groups"
        c="inherit"
        fw={500}
        aria-label={waiting ? `Groups (${waiting} invites waiting)` : undefined}
      >
        Groups
      </Anchor>
    </Indicator>
  )
}

/** Shown in place of every page to a banned account: the API refuses all its requests. */
function Suspended({ message }: { message: string }) {
  const { logout } = useKindeAuth()
  return (
    <Stack align="flex-start" py="xl">
      <Alert color="red" title="Account suspended">
        {message} If you think this is a mistake, email admin@bggroup.app.
      </Alert>
      <Button variant="default" onClick={() => logout()}>
        Sign out
      </Button>
    </Stack>
  )
}

export function Layout() {
  const { isAuthenticated } = useKindeAuth()
  const me = useMe()
  const suspended = me.error instanceof AccountSuspendedError ? me.error : null
  useResumeInvite()

  return (
    <AppShell header={{ height: 56 }} footer={{ height: 44 }} padding="md">
      <AppShell.Header>
        <Container size="md" h="100%">
          <Group h="100%" justify="space-between" wrap="nowrap">
            <Group gap="lg" wrap="nowrap">
              <Anchor component={Link} to="/" underline="never" c="inherit">
                <Title order={3}>Board Game Group</Title>
              </Anchor>
              {isAuthenticated && !suspended && (
                <>
                  <GroupsLink />
                  <Anchor component={NavLink} to="/games" c="inherit" fw={500}>
                    Search
                  </Anchor>
                </>
              )}
            </Group>
            <UserMenu />
          </Group>
        </Container>
      </AppShell.Header>
      <AppShell.Main>
        <Container size="md">
          {suspended ? <Suspended message={suspended.message} /> : <Outlet />}
        </Container>
      </AppShell.Main>
      <AppShell.Footer>
        <Container size="md" h="100%">
          <Group h="100%" justify="center" gap="lg">
            <PoweredByBgg />
            <Anchor component={Link} to="/terms" size="sm" c="dimmed">
              Terms
            </Anchor>
            <Anchor component={Link} to="/privacy" size="sm" c="dimmed">
              Privacy
            </Anchor>
          </Group>
        </Container>
      </AppShell.Footer>
    </AppShell>
  )
}
