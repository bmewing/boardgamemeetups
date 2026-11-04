import {
  Alert,
  Button,
  Card,
  CopyButton,
  Group,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { useEffect, useRef } from 'react'
import { useLocation } from 'react-router'

import {
  feedUrl,
  googleSubscribeUrl,
  useCalendarFeed,
  useMakeCalendarFeed,
  useTurnOffCalendarFeed,
  webcalUrl,
} from '../api/calendar'

/** Your calendar feed: a link to subscribe to from any calendar app. */
export function CalendarFeedCard() {
  const feed = useCalendarFeed()
  const make = useMakeCalendarFeed()
  const off = useTurnOffCalendarFeed()
  const ref = useRef<HTMLDivElement>(null)
  const { hash } = useLocation()

  // The meetup page links here as /groups#calendar.
  useEffect(() => {
    if (hash === '#calendar' && feed.isSuccess) ref.current?.scrollIntoView({ block: 'start' })
  }, [hash, feed.isSuccess])

  const token = feed.data?.token
  const error = feed.error ?? make.error ?? off.error
  return (
    <Card withBorder padding="md" id="calendar" ref={ref}>
      <Stack gap="xs">
        <Title order={4}>Your calendar</Title>
        <Text size="sm" c="dimmed">
          Subscribe from your calendar app to see every date you might go to: the ones you've said
          yes or maybe to, and the ones you haven't answered. Calendar apps only check for changes
          every few hours, so look here for last-minute news.
        </Text>
        {error && <Alert color="red">{error.message}</Alert>}
        {feed.isSuccess && !token && (
          <Group>
            <Button size="xs" loading={make.isPending} onClick={() => make.mutate()}>
              Get a calendar link
            </Button>
          </Group>
        )}
        {token && (
          <>
            <Group gap="xs" wrap="nowrap" align="flex-end">
              <TextInput
                label="Calendar link"
                readOnly
                value={feedUrl(token)}
                onFocus={(e) => e.currentTarget.select()}
                style={{ flex: 1, minWidth: 0 }}
              />
              <CopyButton value={feedUrl(token)}>
                {({ copied, copy }) => (
                  <Button variant="default" onClick={copy}>
                    {copied ? 'Copied' : 'Copy'}
                  </Button>
                )}
              </CopyButton>
            </Group>
            <Group gap="xs">
              <Button size="xs" component="a" href={webcalUrl(token)}>
                Open in calendar app
              </Button>
              <Button
                size="xs"
                variant="light"
                component="a"
                href={googleSubscribeUrl(token)}
                target="_blank"
                rel="noreferrer"
              >
                Add to Google Calendar
              </Button>
            </Group>
            <Text size="xs" c="dimmed">
              Anyone with this link can see your dates and where they are. If it gets out, make a
              new one: the old link stops working.
            </Text>
            <Group gap="xs">
              <Button
                size="xs"
                variant="default"
                loading={make.isPending}
                onClick={() => {
                  if (window.confirm('Make a new link? Calendars using the old one stop updating.'))
                    make.mutate()
                }}
              >
                Make a new link
              </Button>
              <Button
                size="xs"
                variant="subtle"
                color="red"
                loading={off.isPending}
                onClick={() => {
                  if (
                    window.confirm('Turn off your calendar link? Calendars using it stop updating.')
                  )
                    off.mutate()
                }}
              >
                Turn off
              </Button>
            </Group>
          </>
        )}
      </Stack>
    </Card>
  )
}
