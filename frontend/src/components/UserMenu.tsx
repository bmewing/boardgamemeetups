import { useKindeAuth } from '@kinde-oss/kinde-auth-react'
import { Avatar, Button, Group, Menu, UnstyledButton } from '@mantine/core'
import { Link } from 'react-router'

import { useMe } from '../api/me'

export function UserMenu() {
  const { isAuthenticated, isLoading, login, register, logout } = useKindeAuth()
  const me = useMe()

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
  return (
    <Menu position="bottom-end" withinPortal>
      <Menu.Target>
        <UnstyledButton aria-label="Account menu">
          <Avatar src={me.data?.avatar_url} name={name} color="initials" radius="xl" />
        </UnstyledButton>
      </Menu.Target>
      <Menu.Dropdown>
        {name && <Menu.Label>{name}</Menu.Label>}
        <Menu.Item component={Link} to="/collection">
          My games
        </Menu.Item>
        <Menu.Item component={Link} to="/profile">
          Profile
        </Menu.Item>
        <Menu.Item onClick={() => logout()}>Sign out</Menu.Item>
      </Menu.Dropdown>
    </Menu>
  )
}
