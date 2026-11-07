import { Button, Center, Stack, Text } from '@mantine/core'
import type { ReactNode } from 'react'

import { Grouper, type GrouperPose } from './Grouper'

/** Greg beside a short message: for empty lists, dead ends and other quiet moments. */
export function MascotNote({
  pose,
  title,
  children,
  size = 132,
  animated = true,
}: {
  pose: GrouperPose
  title?: ReactNode
  children?: ReactNode
  size?: number
  animated?: boolean
}) {
  return (
    <Stack align="center" gap={6} py="md" ta="center">
      <Grouper pose={pose} size={size} label="" animated={animated} />
      {title && (
        <Text fw={600} size="lg" ff="var(--bgg-font-display)">
          {title}
        </Text>
      )}
      {children}
    </Stack>
  )
}

/**
 * Greg shuffling while something loads. He fades in after a beat, so quick loads don't flash
 * him; the text is announced as a status either way.
 */
export function LoadingNote({
  children = 'Loading…',
  size = 104,
}: {
  children?: ReactNode
  size?: number
}) {
  return (
    <Center py="xl">
      <Stack align="center" gap={4} className="grp-late" role="status">
        <Grouper pose="shuffle" size={size} label="" />
        <Text c="dimmed" size="sm" ta="center">
          {children}
        </Text>
      </Stack>
    </Center>
  )
}

/** Greg, sheepish beside spilled dice, with what went wrong and a way to try again. */
export function ErrorNote({
  error,
  onRetry,
  title = 'That didn’t work',
}: {
  error: Error | string
  onRetry?: () => unknown
  title?: ReactNode
}) {
  return (
    <MascotNote pose="oops" size={112} animated={false} title={title}>
      <Text c="red" size="sm" role="alert" maw={460}>
        {typeof error === 'string' ? error : error.message}
      </Text>
      {onRetry && (
        <Button variant="default" size="sm" mt="xs" onClick={() => onRetry()}>
          Try again
        </Button>
      )}
    </MascotNote>
  )
}
