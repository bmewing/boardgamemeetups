import { Button, Text } from '@mantine/core'
import { Link } from 'react-router'

import { MascotNote } from '../components/mascot/MascotNote'

export function NotFoundPage() {
  return (
    <MascotNote pose="snooze" size={180} title="Nothing at this table">
      <Text c="dimmed">This page doesn't exist. Greg's napping until someone deals him in.</Text>
      <Button component={Link} to="/" mt="sm">
        Back home
      </Button>
    </MascotNote>
  )
}
