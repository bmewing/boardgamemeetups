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
} from '@mantine/core'
import { Link, NavLink, Outlet, useLocation } from 'react-router'

import { useGroups } from '../api/groups'
import { AccountSuspendedError, useMe } from '../api/me'
import { useResumeInvite } from '../auth/pendingInvite'
import classes from './Layout.module.css'
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
    <Indicator disabled={waiting === 0} color="red" size={8} offset={2}>
      <NavLink
        to="/groups"
        className={classes.navLink}
        aria-label={waiting ? `Groups (${waiting} invites waiting)` : undefined}
      >
        Groups
      </NavLink>
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
  const { pathname } = useLocation()
  useResumeInvite()

  // The signed-out home page is a full-width landing page with its own bands.
  const landing = !isAuthenticated && pathname === '/'

  return (
    <AppShell header={{ height: 64 }} footer={{ height: 48 }} padding={landing ? 0 : 'md'}>
      <AppShell.Header className={classes.header}>
        <Container size="md" h="100%">
          <Group h="100%" justify="space-between" wrap="nowrap">
            <Group gap="md" wrap="nowrap">
              <Link to="/" className={classes.brand} aria-label="Board Game Group home">
                <img src="/favicon.svg" alt="" className={classes.logo} />
                <span className={classes.wordmark}>Board Game Group</span>
              </Link>
              {isAuthenticated && !suspended && (
                <Group gap={4} wrap="nowrap">
                  <GroupsLink />
                  <NavLink to="/games" className={classes.navLink}>
                    Search
                  </NavLink>
                </Group>
              )}
            </Group>
            <UserMenu />
          </Group>
        </Container>
      </AppShell.Header>
      <AppShell.Main>
        {landing ? (
          <Outlet />
        ) : (
          <Container size="md" py="sm">
            {suspended ? <Suspended message={suspended.message} /> : <Outlet />}
          </Container>
        )}
      </AppShell.Main>
      <AppShell.Footer className={classes.footer}>
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
