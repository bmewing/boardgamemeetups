import { useKindeAuth } from '@kinde-oss/kinde-auth-react'
import { Avatar, Badge, Button, Group, Indicator, Menu, UnstyledButton } from '@mantine/core'
import { Link } from 'react-router'

import { useFriends } from '../api/friends'
import { useMe } from '../api/me'

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
            <Avatar src={me.data?.avatar_url} name={name} color="initials" radius="xl" />
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
        <Menu.Item onClick={() => logout()}>Sign out</Menu.Item>
      </Menu.Dropdown>
    </Menu>
  )
}
