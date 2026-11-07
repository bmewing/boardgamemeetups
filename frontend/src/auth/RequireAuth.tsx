import { useKindeAuth } from '@kinde-oss/kinde-auth-react'
import { Button, Text } from '@mantine/core'
import type { ReactNode } from 'react'

import { LoadingNote, MascotNote } from '../components/mascot/MascotNote'

export function RequireAuth({ children }: { children: ReactNode }) {
  const { isAuthenticated, isLoading, login } = useKindeAuth()

  if (isLoading) {
    return <LoadingNote />
  }
  if (!isAuthenticated) {
    return (
      <MascotNote pose="wave">
        <Text>Sign in to see this page.</Text>
        <Button onClick={() => login()} mt="xs">
          Sign in
        </Button>
      </MascotNote>
    )
  }
  return children
}
