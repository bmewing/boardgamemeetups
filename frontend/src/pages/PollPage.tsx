import {
  Alert,
  Anchor,
  Badge,
  Button,
  CopyButton,
  Group,
  SegmentedControl,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'

import {
  useClosePoll,
  useDeletePoll,
  usePoll,
  useRemindPoll,
  useReopenPoll,
  useSchedulePoll,
} from '../api/polls'
import { ErrorNote, LoadingNote } from '../components/mascot/MascotNote'
import { Everyone } from '../components/polls/Everyone'
import { MyTimes } from '../components/polls/MyTimes'
import { namesOf } from '../components/polls/pollFormat'
import { NotFoundPage } from './NotFoundPage'

const browserTimeZone = Intl.DateTimeFormat().resolvedOptions().timeZone

export function PollPage() {
  const { pollId = '' } = useParams()
  const poll = usePoll(pollId)
  const navigate = useNavigate()
  const [view, setView] = useState<string | null>(null)
  const close = useClosePoll(pollId)
  const reopen = useReopenPoll(pollId)
  const remind = useRemindPoll(pollId)
  const schedule = useSchedulePoll(pollId)
  const remove = useDeletePoll(pollId, poll.data?.group_id ?? '')

  // Decided once, when the poll first loads: saving your first answer must not flip the view.
  if (view === null && poll.data) {
    setView(poll.data.my_slots === null && poll.data.status === 'open' ? 'mine' : 'everyone')
  }

  if (poll.isPending) return <LoadingNote />
  if (poll.isError) return <ErrorNote error={poll.error} />
  if (poll.data === null) return <NotFoundPage />
  const data = poll.data
  const open = data.status === 'open'
  const answered = data.my_slots !== null
  const current = view ?? 'everyone'
  const zone = data.time_zone.replace(/_/g, ' ')

  return (
    <Stack>
      <Anchor component={Link} to={`/groups/${data.group_id}`} size="sm">
        ← {data.group_name}
      </Anchor>
      <Group gap="sm">
        <Title order={2}>{data.title}</Title>
        {!open && <Badge color="gray">closed</Badge>}
      </Group>
      <Text size="sm" c="dimmed">
        Find a time · {data.respondents.length} answered
        {data.waiting.length > 0 && ` · waiting on ${namesOf(data.waiting)}`}
      </Text>
      {data.time_zone !== browserTimeZone && (
        <Text size="sm" c="meeple">
          Times are in {zone}.
        </Text>
      )}
      {data.meetup_id && (
        <Alert color="green" title="It's scheduled">
          <Button component={Link} to={`/meetups/${data.meetup_id}`} size="xs" mt="xs">
            Open the date
          </Button>
        </Alert>
      )}

      <SegmentedControl
        fullWidth
        value={current}
        onChange={setView}
        data={[
          { value: 'mine', label: answered ? 'My times ✓' : 'My times' },
          { value: 'everyone', label: 'Everyone' },
        ]}
      />

      {open && (
        <Group align="flex-end" wrap="nowrap">
          <TextInput
            flex={1}
            size="xs"
            readOnly
            label="Send this to the group chat"
            value={window.location.href}
            onFocus={(e) => e.currentTarget.select()}
          />
          <CopyButton value={window.location.href}>
            {({ copied, copy }) => (
              <Button size="xs" variant="default" onClick={copy}>
                {copied ? 'Copied' : 'Copy link'}
              </Button>
            )}
          </CopyButton>
        </Group>
      )}
      {data.can_manage && (
        <Group gap="xs">
          {open ? (
            <>
              <Button
                size="compact-sm"
                variant="default"
                loading={remind.isPending}
                disabled={data.waiting.length === 0}
                onClick={() => remind.mutate()}
              >
                Remind those waiting
              </Button>
              <Button
                size="compact-sm"
                variant="default"
                loading={close.isPending}
                onClick={() => close.mutate()}
              >
                Close
              </Button>
            </>
          ) : (
            <Button
              size="compact-sm"
              variant="default"
              loading={reopen.isPending}
              onClick={() => reopen.mutate()}
            >
              Reopen
            </Button>
          )}
          <Button
            size="compact-sm"
            variant="subtle"
            color="red"
            loading={remove.isPending}
            onClick={() => {
              if (!window.confirm(`Delete "${data.title}" and everyone's answers?`)) return
              remove.mutate(undefined, {
                onSuccess: () => navigate(`/groups/${data.group_id}`),
              })
            }}
          >
            Delete
          </Button>
        </Group>
      )}
      {remind.isSuccess && (
        <Text size="sm" c="dimmed">
          Reminder sent.
        </Text>
      )}
      {(remind.isError || schedule.isError || close.isError || remove.isError) && (
        <Text size="sm" c="red">
          {(remind.error ?? schedule.error ?? close.error ?? remove.error)?.message}
        </Text>
      )}

      {current === 'mine' ? (
        // Remounted when the poll opens or closes, so it starts from the server's copy.
        <MyTimes key={`${data.id}:${data.status}`} poll={data} />
      ) : (
        <Everyone
          poll={data}
          scheduling={schedule.isPending}
          onSchedule={(start, label) => {
            if (!window.confirm(`Schedule "${data.title}" for ${label}?`)) return
            schedule.mutate(start, {
              onSuccess: (done) => done.meetup_id && navigate(`/meetups/${done.meetup_id}`),
            })
          }}
        />
      )}
    </Stack>
  )
}
