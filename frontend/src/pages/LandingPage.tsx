import { useKindeAuth } from '@kinde-oss/kinde-auth-react'
import { Button, Group } from '@mantine/core'
import type { ReactNode } from 'react'

import { Die } from '../components/landing/Die'
import { Meeple } from '../components/landing/Meeple'
import { useInView } from '../components/landing/motion'
import { TonightsPickDemo } from '../components/landing/TonightsPickDemo'
import { Grouper } from '../components/mascot/Grouper'
import { palette } from '../theme'
import classes from './LandingPage.module.css'

/** Fades and hops its children in the first time they scroll into view. */
function Reveal({ children, className }: { children: ReactNode; className?: string }) {
  const { ref, inView } = useInView<HTMLDivElement>()
  return (
    <div
      ref={ref}
      className={`${classes.reveal} ${className ?? ''}`}
      data-shown={inView || undefined}
    >
      {children}
    </div>
  )
}

const STEPS = [
  {
    color: palette.coral,
    title: 'Gather your crew',
    body: 'Start a group, send an invite link, and set a schedule: every other Thursday, first Saturday, whatever sticks.',
  },
  {
    color: palette.navy,
    title: 'Pool your shelves',
    body: "Pull your collection from BoardGameGeek or upload a spreadsheet. Everyone's games land in one shared library.",
  },
  {
    color: palette.teal,
    title: 'RSVP with a mood',
    body: "Say you're in, bring a plus-one, and tell the table what you're in the mood for tonight.",
  },
  {
    color: '#c9a94b',
    title: 'Vote and play',
    body: 'See the games that fit the headcount and the mood, vote on what hits the table, and log who won.',
  },
]

const EXTRAS = [
  'Calendar feed for every date',
  'Reminders the day before',
  "Who's bringing what",
  'Who can teach it',
  'Play log and bragging rights',
]

export function LandingPage() {
  const { login, register } = useKindeAuth()

  return (
    <div className={classes.page}>
      <section className={classes.hero}>
        <div className={classes.inner}>
          <div className={classes.heroCopy}>
            <span className={classes.badge}>Thursday · 7 pm · 5 going</span>
            <h1 className={classes.heroTitle}>
              Game night,
              <br />
              <span className={classes.accent}>sorted.</span>
            </h1>
            <p className={classes.heroSub}>
              See who's coming, pool everyone's shelves, and let the table pick what to play. Less
              "so… what do you want to play?", more playing.
            </p>
            <Group gap="sm">
              <Button size="lg" onClick={() => register()}>
                Get started
              </Button>
              <Button size="lg" variant="default" onClick={() => login()}>
                Sign in
              </Button>
            </Group>
            <p className={classes.heroNote}>
              Bring your collection from BoardGameGeek or a spreadsheet.
            </p>
          </div>
          <div className={classes.heroArt}>
            <Grouper pose="toss" size={360} className={classes.heroFish} />
            <div className={classes.heroDie}>
              <Die size={64} />
              <span className={classes.dieHint}>go on, roll it</span>
            </div>
          </div>
        </div>
      </section>

      <section className={classes.section}>
        <div className={classes.inner}>
          <Reveal>
            <p className={classes.kicker}>How it plays</p>
            <h2 className={classes.title}>Four steps from group chat to game table.</h2>
          </Reveal>
          <div className={classes.steps}>
            {STEPS.map((step, i) => (
              <Reveal key={step.title} className={classes.stepWrap}>
                <article className={classes.step}>
                  <div className={classes.stepHead} style={{ background: step.color }}>
                    <span className={classes.stepNum}>{i + 1}</span>
                    <Meeple
                      color="#fffaf3"
                      outline={palette.olive}
                      width={34}
                      height={34}
                      className={classes.stepMeeple}
                    />
                  </div>
                  <h3 className={classes.stepTitle}>{step.title}</h3>
                  <p className={classes.stepBody}>{step.body}</p>
                </article>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      <section className={`${classes.section} ${classes.band}`}>
        <div className={classes.inner}>
          <Reveal>
            <p className={classes.kicker}>Live demo</p>
            <h2 className={classes.title}>Watch a game night come together.</h2>
            <p className={classes.sub}>
              Every meetup runs this loop: RSVPs come in, shelves pool, games that don't fit the
              headcount drop out, and the table votes on the rest.
            </p>
          </Reveal>
          <TonightsPickDemo />
          <ul className={classes.extras}>
            {EXTRAS.map((extra) => (
              <li key={extra} className={classes.extra}>
                <Meeple color={palette.teal} width={16} height={16} />
                {extra}
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className={classes.cta}>
        <div className={`${classes.inner} ${classes.ctaInner}`}>
          <Die size={72} tone="coral" />
          <h2 className={classes.ctaTitle}>Your table is waiting.</h2>
          <p className={classes.ctaSub}>
            Start a group in a minute, then send the invite link to your crew.
          </p>
          <Button size="lg" color="coral" className={classes.ctaButton} onClick={() => register()}>
            Start a group
          </Button>
        </div>
      </section>
    </div>
  )
}
