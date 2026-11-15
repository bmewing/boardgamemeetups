import { Badge, Button, Card, Group, Stack, Text } from '@mantine/core'
import { useEffect, useRef, useState } from 'react'

import type { Poll } from '../../api/polls'
import { useSaveAnswer } from '../../api/polls'
import { dayLabel, timeLabel } from './pollFormat'
import classes from './polls.module.css'

const SAVE_DELAY_MS = 600

/** The picker: tap every half hour you could make. There's no submit button; each tap
 *  restarts a short timer and the whole set is saved when it fires. */
export function MyTimes({ poll }: { poll: Poll }) {
  const open = poll.status === 'open'
  const [picked, setPicked] = useState(() => new Set(poll.my_slots ?? []))
  const [answeredOnArrival] = useState(poll.my_slots !== null)
  const [answered, setAnswered] = useState(answeredOnArrival)
  const [dirty, setDirty] = useState(false)
  const save = useSaveAnswer(poll.id)

  // What the timer sends is whatever is current when it fires, not when it was set.
  const latest = useRef(picked)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const pending = useRef(false)
  const send = useRef<(slots: string[]) => void>(() => {})
  useEffect(() => {
    send.current = (slots: string[]) => {
      save.mutate(slots, {
        onSuccess: () => {
          if (!pending.current) setDirty(false)
        },
      })
    }
  })

  useEffect(
    () => () => {
      // Leaving with a save waiting: send it now rather than lose it.
      if (timer.current) {
        clearTimeout(timer.current)
        timer.current = null
        send.current([...latest.current])
      }
    },
    [],
  )

  const change = (next: Set<string>) => {
    latest.current = next
    setPicked(next)
    setAnswered(true)
    setDirty(true)
    pending.current = true
    if (timer.current) clearTimeout(timer.current)
    timer.current = setTimeout(() => {
      timer.current = null
      pending.current = false
      send.current([...latest.current])
    }, SAVE_DELAY_MS)
  }

  const toggle = (slot: string) => {
    const next = new Set(picked)
    if (next.has(slot)) next.delete(slot)
    else next.add(slot)
    change(next)
  }

  const setDay = (slots: string[], on: boolean) => {
    const next = new Set(picked)
    for (const slot of slots) {
      if (on) next.add(slot)
      else next.delete(slot)
    }
    change(next)
  }

  // How many others picked each slot, so you can see where the group is leaning.
  const others = new Map<string, number>()
  for (const r of poll.respondents) {
    for (const slot of r.slots) others.set(slot, (others.get(slot) ?? 0) + 1)
  }
  const mine = new Set(poll.my_slots ?? [])
  const saving = dirty || save.isPending

  return (
    <Stack>
      <div className={classes.sticky}>
        <Group justify="space-between" wrap="nowrap">
          <Text size="sm">
            {open ? (
              <>
                Tap every time you could make it. <b>{picked.size} picked.</b>
              </>
            ) : (
              'This poll is closed.'
            )}
          </Text>
          {open && answered && (
            <Badge color={saving ? 'gray' : 'green'} variant="light">
              {saving ? 'Saving…' : 'Saved'}
            </Badge>
          )}
        </Group>
        {save.isError && (
          <Text size="sm" c="red">
            {save.error.message}
          </Text>
        )}
      </div>
      {open && !answeredOnArrival && (
        // Hidden, not removed, once you've tapped: the slots below must not jump under your finger.
        <Button
          variant="default"
          style={answered ? { visibility: 'hidden' } : undefined}
          tabIndex={answered ? -1 : 0}
          onClick={() => change(new Set())}
        >
          None of these work for me
        </Button>
      )}
      {poll.days.map((day) => {
        const allOn = day.slots.every((s) => picked.has(s))
        return (
          <Card key={day.date} withBorder padding="sm">
            <Stack gap="xs">
              <Group justify="space-between">
                <Text fw={600}>{dayLabel(day.date)}</Text>
                {open && (
                  <Button
                    size="compact-xs"
                    variant="subtle"
                    onClick={() => setDay(day.slots, !allOn)}
                  >
                    {allOn ? 'Clear' : 'All'}
                  </Button>
                )}
              </Group>
              <div className={classes.grid}>
                {day.slots.map((slot) => {
                  const on = picked.has(slot)
                  const free = (others.get(slot) ?? 0) - (mine.has(slot) ? 1 : 0)
                  return (
                    <button
                      key={slot}
                      type="button"
                      aria-pressed={on}
                      disabled={!open}
                      className={`${classes.slot} ${on ? classes.picked : ''}`}
                      onClick={() => toggle(slot)}
                    >
                      <span className={classes.time}>{timeLabel(slot)}</span>
                      <span className={classes.note}>
                        {on ? '✓' : free > 0 ? `${free} free` : ''}
                      </span>
                    </button>
                  )
                })}
              </div>
            </Stack>
          </Card>
        )
      })}
    </Stack>
  )
}
