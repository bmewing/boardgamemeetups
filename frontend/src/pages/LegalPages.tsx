import { Anchor, List, Stack, Text, Title } from '@mantine/core'
import type { ReactNode } from 'react'
import { Link } from 'react-router'

// Open to anyone, signed in or not: sign-in providers (Discord, Google, Facebook) link here.
export const UPDATED = 'November 4, 2026'
export const CONTACT = 'admin@bggroup.app'

function Section({ title, id, children }: { title: string; id?: string; children: ReactNode }) {
  return (
    <Stack gap="xs" id={id}>
      <Title order={3}>{title}</Title>
      {children}
    </Stack>
  )
}

function Contact() {
  return <Anchor href={`mailto:${CONTACT}`}>{CONTACT}</Anchor>
}

function Page({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Stack maw={720} gap="lg" pb="xl">
      <Stack gap={4}>
        <Title order={2}>{title}</Title>
        <Text size="sm" c="dimmed">
          Last updated {UPDATED}
        </Text>
      </Stack>
      {children}
    </Stack>
  )
}

export function PrivacyPage() {
  return (
    <Page title="Privacy policy">
      <Text>
        Board Game Group (bggroup.app) helps groups of friends plan game nights: who's coming, which
        games to play and who brings them. It's a small, free app run by one person. This page says
        what it keeps about you, who can see it, and how to remove it. Questions go to <Contact />.
      </Text>

      <Section title="What we keep">
        <List spacing="xs">
          <List.Item>
            <b>Your account:</b> your email address, name and profile picture from the way you sign
            in (email, Google, Facebook or Discord), plus the username, time zone and BoardGameGeek
            username you choose.
          </List.Item>
          <List.Item>
            <b>Your games:</b> what you own, want or have played, and your ratings, notes and other
            answers about games, whether you type them in, upload a file or pull them from
            BoardGameGeek.
          </List.Item>
          <List.Item>
            <b>Friends and groups:</b> who you're friends with or have blocked, the groups you're
            in, the dates they meet (including where), your answers to those dates, guests you're
            bringing, votes, the games you're bringing, and what was played and who won.
          </List.Item>
          <List.Item>
            <b>Invites:</b> email addresses you invite to a group, so the invite can wait until that
            person signs up.
          </List.Item>
          <List.Item>
            <b>Email settings:</b> which kinds of email you've turned off.
          </List.Item>
        </List>
        <Text>
          There are no ads, no analytics and no tracking. The app stores a little in your browser to
          keep you signed in and to remember an invite link while you sign up, and nothing else.
        </Text>
      </Section>

      <Section title="Who can see it">
        <List spacing="xs">
          <List.Item>
            Other people see your username and picture, and can find you by typing your username or
            your exact email address. <b>Nobody else is ever shown your email address.</b>
          </List.Item>
          <List.Item>
            Your game list is visible to you only, to your friends, or to everyone signed in, as you
            choose on your profile.
          </List.Item>
          <List.Item>
            Joining a group shares your games and your answers about them with its members, whatever
            your profile setting says. <b>Your notes are never shown to anyone.</b>
          </List.Item>
          <List.Item>
            A group's dates, places and who's coming are shown only to its members.
          </List.Item>
          <List.Item>
            Your calendar feed link shows your upcoming dates to anyone who has the link. You can
            turn it off or replace it any time.
          </List.Item>
        </List>
      </Section>

      <Section title="Services that handle it for us">
        <Text>We don't sell or rent your information. These services help run the app:</Text>
        <List spacing="xs">
          <List.Item>
            <b>Kinde</b> handles signing in and holds your sign-in account.
          </List.Item>
          <List.Item>
            <b>Supabase</b> stores the app's database, and <b>DigitalOcean</b> runs the app.
          </List.Item>
          <List.Item>
            <b>Resend</b> sends the app's emails.
          </List.Item>
          <List.Item>
            <b>BoardGameGeek</b> supplies game details. If you pull your collection, your
            BoardGameGeek username is sent to it to look up your games.
          </List.Item>
          <List.Item>
            <b>Google, Facebook or Discord</b>, if you sign in with one of them, tell us your name,
            email address and picture. We ask for nothing else, and never post anything for you.
          </List.Item>
        </List>
      </Section>

      <Section title="Emails">
        <Text>
          The app emails you about friend requests, group invites, dates you haven't answered, dates
          that change, and games picked or that you're bringing. Each kind can be turned off on your{' '}
          <Anchor component={Link} to="/profile">
            profile
          </Anchor>{' '}
          or from a link in any email. Someone you invite who isn't on the app gets one email about
          that invite.
        </Text>
      </Section>

      <Section title="Deleting your data" id="delete">
        <Text>
          Delete your account from the bottom of your{' '}
          <Anchor component={Link} to="/profile">
            profile page
          </Anchor>
          . That removes your profile, games, answers, friends, group memberships and your part in
          your groups' dates and plays straight away. Any group you own is handed to its
          longest-serving admin, or member, and deleted if nobody else is in it. Invites you sent
          and games you nominated stay with the group without your name.
        </Text>
        <Text>
          Your sign-in account at Kinde is separate. To remove it too, or if you can't sign in,
          email <Contact /> from the address you signed up with and it will be deleted within 30
          days.
        </Text>
      </Section>

      <Section title="Children">
        <Text>
          The app isn't meant for children under 13, and doesn't knowingly keep their data.
        </Text>
      </Section>

      <Section title="Changes">
        <Text>
          If this policy changes, the date at the top changes too. Big changes will be emailed to
          you first.
        </Text>
      </Section>
    </Page>
  )
}

export function TermsPage() {
  return (
    <Page title="Terms of service">
      <Text>
        These terms cover using Board Game Group (bggroup.app). By signing in, you agree to them.
        The{' '}
        <Anchor component={Link} to="/privacy">
          privacy policy
        </Anchor>{' '}
        says what the app keeps about you.
      </Text>

      <Section title="The app">
        <Text>
          Board Game Group is free, run by one person, and offered as it is. It may change, have
          bugs or be unavailable at times, and it could shut down; if it does, you'll be told by
          email first where possible. Don't rely on it for anything you can't afford to miss, like
          the only record of where a game night is.
        </Text>
      </Section>

      <Section title="Your account">
        <List spacing="xs">
          <List.Item>You need to be at least 13 to use it.</List.Item>
          <List.Item>
            Keep your sign-in to yourself. You're responsible for what's done with your account.
          </List.Item>
          <List.Item>
            Pick a username that isn't offensive and doesn't pretend to be someone else.
          </List.Item>
        </List>
      </Section>

      <Section title="What you put in">
        <Text>
          What you add (your games, answers, notes, group details) stays yours. You let the app
          store it and show it to the people the privacy policy and your settings allow, only to run
          the app. Only add addresses and other details about people that they're happy to share
          with the group.
        </Text>
      </Section>

      <Section title="Please don't">
        <List spacing="xs">
          <List.Item>Harass, threaten or spam anyone, including through invites.</List.Item>
          <List.Item>
            Post anything illegal, or anything you don't have the right to share.
          </List.Item>
          <List.Item>
            Try to get into other people's accounts or data, or break, overload or scrape the app.
          </List.Item>
        </List>
        <Text>
          Accounts that do may be suspended or removed. If someone is bothering you, block them from
          your Friends page and let <Contact /> know.
        </Text>
      </Section>

      <Section title="Game information">
        <Text>
          Game details and images come from{' '}
          <Anchor href="https://boardgamegeek.com" target="_blank" rel="noreferrer">
            BoardGameGeek
          </Anchor>{' '}
          and belong to their owners. Recommendations are suggestions, not promises that your group
          will enjoy a game.
        </Text>
      </Section>

      <Section title="Responsibility">
        <Text>
          The app is provided without warranties of any kind. As far as the law allows, whoever runs
          it isn't liable for losses that come from using it or not being able to, including lost
          data or a missed game night. Game nights themselves are between you and the people you
          meet.
        </Text>
      </Section>

      <Section title="Ending">
        <Text>
          You can stop using the app and delete your account any time from your profile. If these
          terms change, the date at the top changes too, and big changes will be emailed to you
          first. Questions go to <Contact />.
        </Text>
      </Section>
    </Page>
  )
}
