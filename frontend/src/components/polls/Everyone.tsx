import { Alert, Button, Card, Stack, Text } from '@mantine/core'
import { useState } from 'react'

import type { Poll } from '../../api/polls'
import { dayLabel, namesOf, stretchLabel, timeLabel } from './pollFormat'
import classes from './polls.module.css'

/** Best times, then every half hour as a heat map; tap a time to see who's free. */
export function Everyone({
  poll,
  scheduling,
  onSchedule,
}: {
  poll: Poll
  scheduling: boolean
  onSchedule: (start: string, label: string) => void
}) {
  const [focused, setFocused] = useState<string | null>(null)
  const total = poll.respondents.length
  const freeAt = (slot: string) => poll.respondents.filter((r) => r.slots.includes(slot))
  const canSchedule = poll.can_manage && poll.status === 'open'

  const focusedFree = focused ? freeAt(focused).map((r) => r.person) : []

  return (
    <Stack>
      <Card withBorder padding="md">
        <Stack gap="sm">
          <Text fw={600}>Best times</Text>
          {total === 0 ? (
            <Text c="dimmed">Nobody has answered yet.</Text>
          ) : poll.best.length === 0 ? (
            <Text c="dimmed">There&apos;s no time that works for anyone yet.</Text>
          ) : (
            poll.best.map((best, i) => {
              const label = stretchLabel(best.start, best.end)
              const everyone = best.missing.length === 0
              return (
                <Stack
                  key={best.start}
                  gap={4}
                  p="xs"
                  style={{
                    borderRadius: 'var(--mantine-radius-md)',
                    border:
                      i === 0
                        ? '2px solid var(--mantine-primary-color-filled)'
                        : '1px solid var(--mantine-color-default-border)',
                  }}
                >
                  <Text fw={600}>{label}</Text>
                  {everyone ? (
                    <Text size="sm" c="green">
                      Everyone who answered ({best.available.length})
                    </Text>
                  ) : (
                    <Text size="sm">
                      {best.available.length} of {total}: {namesOf(best.available)}
                    </Text>
                  )}
                  {best.missing.length > 0 && (
                    <Text size="xs" c="dimmed">
                      Can&apos;t make all of it: {namesOf(best.missing)}
                    </Text>
                  )}
                  {canSchedule && (
                    <div>
                      <Button
                        size="compact-sm"
                        variant={i === 0 ? 'filled' : 'light'}
                        loading={scheduling}
                        onClick={() => onSchedule(best.start, label)}
                      >
                        Schedule it
                      </Button>
                    </div>
                  )}
                </Stack>
              )
            })
          )}
        </Stack>
      </Card>

      <Card withBorder padding="md">
        <Stack gap="sm">
          <Text fw={600}>Every half hour</Text>
          <Text size="xs" c="dimmed">
            Brighter means more people are free. Tap a time to see who.
          </Text>
          {focused && (
            <Alert
              variant="light"
              p="xs"
              withCloseButton
              closeButtonLabel="Dismiss"
              onClose={() => setFocused(null)}
            >
              {dayLabel(focused.split('T')[0])} at {timeLabel(focused)}.{' '}
              {focusedFree.length ? `Free: ${namesOf(focusedFree)}` : 'Nobody is free then.'}
            </Alert>
          )}
          {poll.days.map((day) => (
            <Stack key={day.date} gap="xs">
              <Text fw={500} size="sm">
                {dayLabel(day.date)}
              </Text>
              <div className={classes.grid}>
                {day.slots.map((slot) => {
                  const free = freeAt(slot).length
                  const heat = total ? free / total : 0
                  const full = total > 0 && free === total
                  return (
                    <button
                      key={slot}
                      type="button"
                      aria-pressed={focused === slot}
                      className={`${classes.slot} ${classes.heat} ${full ? classes.full : ''} ${focused === slot ? classes.focused : ''}`}
                      style={{ '--heat': heat } as React.CSSProperties}
                      onClick={() => setFocused(focused === slot ? null : slot)}
                    >
                      <span className={classes.time}>{timeLabel(slot)}</span>
                      <span className={classes.note}>
                        {free}/{total}
                      </span>
                    </button>
                  )
                })}
              </div>
            </Stack>
          ))}
        </Stack>
      </Card>
    </Stack>
  )
}
