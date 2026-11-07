import { Alert, Badge, Button, Group, Skeleton } from '@mantine/core'
import type { ReactNode } from 'react'
import { Link } from 'react-router'

import { useMyGames } from '../api/collection'
import { useFriends } from '../api/friends'
import { type GroupSummary, type MeetupBrief, useGroups } from '../api/groups'
import { useMe } from '../api/me'
import { MeepleHex } from '../components/landing/MeepleHex'
import { PlayerPiece } from '../components/pieces/PlayerPiece'
import {
  calendarDate,
  endTime,
  formatShortDate,
  formatTime,
  ROLE_LABELS,
} from '../components/meetupFormat'
import { plural } from '../components/userGameFields'
import classes from './Dashboard.module.css'

const MAX_SEATS = 8

function greeting(hour = new Date().getHours()) {
  if (hour < 5) return 'Up late'
  if (hour < 12) return 'Morning'
  if (hour < 17) return 'Afternoon'
  return 'Evening'
}

type Upcoming = { group: GroupSummary; meetup: MeetupBrief }

/** Each group's next date that's still on, soonest first. */
function upcoming(groups: GroupSummary[]): Upcoming[] {
  return groups
    .flatMap((group) =>
      group.next_meetup && group.next_meetup.status === 'scheduled'
        ? [{ group, meetup: group.next_meetup }]
        : [],
    )
    .sort((a, b) => a.meetup.starts_at.localeCompare(b.meetup.starts_at))
}

const ANSWERS = { yes: "You're going", maybe: 'Maybe', no: "Can't make it" } as const

function Panel({
  title,
  action,
  children,
}: {
  title: string
  action?: ReactNode
  children: ReactNode
}) {
  return (
    <section className={classes.panel}>
      <div className={classes.panelHead}>
        <h2 className={classes.panelTitle}>{title}</h2>
        {action}
      </div>
      {children}
    </section>
  )
}

/** Who's going, as their pieces around the table; the guests they bring are plain meeples. */
function Seats({ meetup }: { meetup: MeetupBrief }) {
  const count = meetup.headcount
  const guests = Math.max(count - meetup.going.length, 0)
  const seats = [
    ...meetup.going.map((person) => ({ key: person.id, person, name: person.display_name })),
    ...Array.from({ length: guests }, (_, i) => ({
      key: `guest-${i}`,
      person: { id: `guest-${i}`, piece: 'meeple' as const, piece_color: 'cream' as const },
      name: 'A guest',
    })),
  ].slice(0, MAX_SEATS)
  return (
    <div className={classes.seats} aria-label={plural(count, 'person', 'people') + ' going'}>
      {seats.map((seat, i) => (
        <PlayerPiece
          key={seat.key}
          person={seat.person}
          size={26}
          label=""
          className={classes.seat}
          style={{ animationDelay: `${i * 70}ms` }}
        />
      ))}
      {count > MAX_SEATS && <span className={classes.more}>+{count - MAX_SEATS}</span>}
      {count === 0 && <span className={classes.empty}>No one yet. Be the first.</span>}
    </div>
  )
}

/** The next game night, drawn as a ticket. */
function NextUp({ next }: { next: Upcoming }) {
  const { group, meetup } = next
  const day = calendarDate(meetup.local_date)
  const answered = meetup.my_response
  return (
    <Link to={`/meetups/${meetup.id}`} className={classes.ticket}>
      <div className={classes.stub}>
        <span className={classes.stubWeekday}>
          {day.toLocaleDateString(undefined, { weekday: 'short' })}
        </span>
        <span className={classes.stubDay}>{day.getDate()}</span>
        <span className={classes.stubMonth}>
          {day.toLocaleDateString(undefined, { month: 'short' })}
        </span>
      </div>
      <div className={classes.ticketBody}>
        <span className={classes.ticketKicker}>Next game night</span>
        <span className={classes.ticketGroup}>{group.name}</span>
        <span className={classes.ticketMeta}>
          {formatTime(meetup.local_time)} – {endTime(meetup.local_time, meetup.duration_minutes)}
          {meetup.location ? ` · ${meetup.location}` : ''}
        </span>
        <Seats meetup={meetup} />
        <Group gap="xs" mt={4}>
          {answered ? (
            <Badge variant="light" color={answered === 'no' ? 'gray' : 'meeple'} size="lg">
              {ANSWERS[answered]}
            </Badge>
          ) : (
            <span className={classes.ask}>Are you coming? Tap to answer</span>
          )}
          {meetup.maybe > 0 && (
            <span className={classes.ticketMeta}>{plural(meetup.maybe, 'maybe', 'maybes')}</span>
          )}
        </Group>
      </div>
    </Link>
  )
}

function NothingPlanned({ hasGroups }: { hasGroups: boolean }) {
  return (
    <div className={classes.nothing}>
      <MeepleHex size={96} />
      <div>
        <p className={classes.nothingTitle}>
          {hasGroups ? 'Nothing on the calendar yet' : 'Start your first group'}
        </p>
        <p className={classes.muted}>
          {hasGroups
            ? 'Add a date to one of your groups and everyone gets asked if they can make it.'
            : 'Make a group, send the invite link to your crew, and set when you meet.'}
        </p>
        <Button component={Link} to="/groups" mt="sm">
          {hasGroups ? 'Go to your groups' : 'Start a group'}
        </Button>
      </div>
    </div>
  )
}

function GroupRow({ group }: { group: GroupSummary }) {
  const next = group.next_meetup
  return (
    <Link to={`/groups/${group.id}`} className={classes.groupRow}>
      <span className={classes.groupDot} aria-hidden="true" />
      <span className={classes.groupText}>
        <span className={classes.groupName}>{group.name}</span>
        <span className={classes.muted}>
          {next && next.status === 'scheduled'
            ? `${formatShortDate(next.local_date)} · ${formatTime(next.local_time)} · ${next.headcount} going`
            : 'No dates coming up'}
        </span>
      </span>
      {group.my_role !== 'member' && (
        <Badge size="sm" variant="light">
          {ROLE_LABELS[group.my_role]}
        </Badge>
      )}
    </Link>
  )
}

type Todo = { key: string; to: string; label: string; detail: string }

function WaitingOnYou({ todos }: { todos: Todo[] }) {
  if (todos.length === 0) return null
  return (
    <Panel title="Waiting on you">
      <ul className={classes.todos}>
        {todos.map((todo) => (
          <li key={todo.key}>
            <Link to={todo.to} className={classes.todo}>
              <span className={classes.todoPip} aria-hidden="true" />
              <span className={classes.groupText}>
                <span className={classes.groupName}>{todo.label}</span>
                <span className={classes.muted}>{todo.detail}</span>
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </Panel>
  )
}

function Shelf() {
  const games = useMyGames()
  const friends = useFriends()

  if (games.isPending) return <Skeleton h={180} radius="lg" />
  const owned = (games.data ?? []).filter((g) => g.ownership === 'owned' && !g.game.is_expansion)
  const favorites = [...owned]
    .filter((g) => g.game.thumbnail_url)
    .sort((a, b) => (b.rating ?? b.game.bgg_rating ?? 0) - (a.rating ?? a.game.bgg_rating ?? 0))
    .slice(0, 6)
  const wantToPlay = (games.data ?? []).filter((g) => g.want_to_play).length
  const plays = (games.data ?? []).reduce((sum, g) => sum + g.plays, 0)
  const friendCount = friends.data?.friends.length ?? 0

  return (
    <Panel
      title="Your shelf"
      action={
        <Button component={Link} to="/collection" size="xs" variant="light">
          My games
        </Button>
      }
    >
      {owned.length === 0 ? (
        <div>
          <p className={classes.muted}>
            Bring your games in so your groups know what's on the shelf.
          </p>
          <Group gap="xs" mt="sm">
            <Button component={Link} to="/collection/pull" size="sm">
              Pull from BGG
            </Button>
            <Button component={Link} to="/collection/import" size="sm" variant="default">
              Import a file
            </Button>
          </Group>
        </div>
      ) : (
        <>
          <div className={classes.stats}>
            <div className={classes.stat}>
              <span className={classes.statNum}>{owned.length}</span>
              <span className={classes.statLabel}>games</span>
            </div>
            <div className={classes.stat}>
              <span className={classes.statNum}>{wantToPlay}</span>
              <span className={classes.statLabel}>want to play</span>
            </div>
            <div className={classes.stat}>
              <span className={classes.statNum}>{plays}</span>
              <span className={classes.statLabel}>plays logged</span>
            </div>
          </div>
          {favorites.length > 0 && (
            <div className={classes.boxes}>
              {favorites.map((g) => (
                <Link
                  key={g.game.id}
                  to={`/games/${g.game.id}`}
                  className={classes.box}
                  title={g.game.name}
                >
                  <img src={g.game.thumbnail_url!} alt={g.game.name} loading="lazy" />
                </Link>
              ))}
            </div>
          )}
        </>
      )}
      <Link to="/friends" className={classes.friendsLink}>
        {friendCount === 0 ? 'Find your friends' : `${plural(friendCount, 'friend')} on here`} →
      </Link>
    </Panel>
  )
}

/** The signed-in home page: what's next, what needs an answer, and your groups and shelf. */
export function Dashboard({ footer }: { footer?: ReactNode }) {
  const me = useMe()
  const groups = useGroups()
  const friends = useFriends()

  const list = groups.data?.groups ?? []
  const dates = upcoming(list)
  const next = dates[0]

  const todos: Todo[] = [
    ...(groups.data?.invites ?? []).map((invite) => ({
      key: `invite-${invite.id}`,
      to: '/groups',
      label: `Join ${invite.group_name}?`,
      detail: invite.invited_by
        ? `${invite.invited_by.display_name} invited you`
        : 'You have an invite',
    })),
    ...dates
      .filter(({ meetup }) => meetup.my_response === null)
      .map(({ group, meetup }) => ({
        key: `rsvp-${meetup.id}`,
        to: `/meetups/${meetup.id}`,
        label: `Coming to ${group.name}?`,
        detail: `${formatShortDate(meetup.local_date)} · ${formatTime(meetup.local_time)}`,
      })),
    ...((friends.data?.incoming.length ?? 0) > 0
      ? [
          {
            key: 'friends',
            to: '/friends',
            label: plural(friends.data!.incoming.length, 'friend request'),
            detail: 'Say yes to share collections',
          },
        ]
      : []),
  ]

  const name = me.data?.display_name
  return (
    <div className={classes.page}>
      <header className={classes.hello}>
        <div>
          <h1 className={classes.helloTitle}>
            {greeting()}
            {name ? `, ${name}` : ''}
          </h1>
          <p className={classes.helloSub}>
            {groups.isPending
              ? 'Checking the calendar…'
              : next
                ? `Next up: ${next.group.name}, ${formatShortDate(next.meetup.local_date)}. ${next.meetup.headcount} going so far.`
                : 'Nothing on the calendar yet. Time to fix that.'}
          </p>
        </div>
      </header>

      {groups.isError && <Alert color="red">{groups.error.message}</Alert>}

      <div className={classes.grid}>
        <div className={classes.main}>
          {groups.isPending ? (
            <Skeleton h={190} radius="lg" />
          ) : next ? (
            <NextUp next={next} />
          ) : (
            <NothingPlanned hasGroups={list.length > 0} />
          )}

          {list.length > 0 && (
            <Panel
              title="Your groups"
              action={
                <Button component={Link} to="/groups" size="xs" variant="light">
                  All groups
                </Button>
              }
            >
              <div className={classes.groups}>
                {list.map((group) => (
                  <GroupRow key={group.id} group={group} />
                ))}
              </div>
            </Panel>
          )}
        </div>

        <div className={classes.side}>
          <WaitingOnYou todos={todos} />
          <Shelf />
        </div>
      </div>

      {footer}
    </div>
  )
}
