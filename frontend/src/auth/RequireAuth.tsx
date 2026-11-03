import { useKindeAuth } from '@kinde-oss/kinde-auth-react'
import { Button, Center, Loader, Stack, Text } from '@mantine/core'
import type { ReactNode } from 'react'

export function RequireAuth({ children }: { children: ReactNode }) {
  const { isAuthenticated, isLoading, login } = useKindeAuth()

  if (isLoading) {
    return (
      <Center py="xl">
        <Loader />
      </Center>
    )
  }
  if (!isAuthenticated) {
    return (
      <Stack align="center" py="xl">
        <Text>Sign in to see this page.</Text>
        <Button onClick={() => login()}>Sign in</Button>
      </Stack>
    )
  }
  return children
}
