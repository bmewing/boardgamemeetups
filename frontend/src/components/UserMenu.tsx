import { useKindeAuth } from '@kinde-oss/kinde-auth-react'
import { Badge, Button, Group, Indicator, Menu, UnstyledButton } from '@mantine/core'
import { Link } from 'react-router'

import { useFriends } from '../api/friends'
import { useMe } from '../api/me'
import { PlayerPiece } from './pieces/PlayerPiece'

export function UserMenu() {
  const { isAuthenticated, isLoading, login, register, logout } = useKindeAuth()
  const me = useMe()
  const friends = useFriends()

  if (isLoading) return null
  if (!isAuthenticated) {
    return (
      <Group gap="xs">
        <Button variant="subtle" onClick={() => login()}>
          Sign in
        </Button>
        <Button onClick={() => register()}>Create account</Button>
      </Group>
    )
  }

  const name = me.data?.display_name ?? ''
  const asking = friends.data?.incoming.length ?? 0
  return (
    <Menu position="bottom-end" withinPortal>
      <Menu.Target>
        <UnstyledButton aria-label="Account menu">
          <Indicator disabled={asking === 0} color="red" size={10} offset={4}>
            {me.data ? (
              <PlayerPiece person={me.data} size={38} label="" />
            ) : (
              <span style={{ display: 'block', width: 38, height: 38 }} />
            )}
          </Indicator>
        </UnstyledButton>
      </Menu.Target>
      <Menu.Dropdown>
        {name && <Menu.Label>{name}</Menu.Label>}
        <Menu.Item component={Link} to="/collection">
          My games
        </Menu.Item>
        <Menu.Item
          component={Link}
          to="/friends"
          rightSection={
            asking > 0 && (
              <Badge size="sm" color="red" circle aria-label={`${asking} friend requests`}>
                {asking}
              </Badge>
            )
          }
        >
          Friends
        </Menu.Item>
        <Menu.Item component={Link} to="/profile">
          Profile
        </Menu.Item>
        {me.data?.is_admin && (
          <Menu.Item component={Link} to="/admin">
            Admin
          </Menu.Item>
        )}
        <Menu.Item onClick={() => logout()}>Sign out</Menu.Item>
      </Menu.Dropdown>
    </Menu>
  )
}
