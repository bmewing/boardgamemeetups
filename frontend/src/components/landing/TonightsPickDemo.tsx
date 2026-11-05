import { useEffect, useState, type CSSProperties } from 'react'

import { palette } from '../../theme'
import { Die } from './Die'
import { Meeple } from './Meeple'
import { prefersReducedMotion, useInView } from './motion'
import { dealRound, HEADCOUNT, LABELS, nextGame, PLAYERS, ranking, type Game } from './pickDemo'
import classes from './TonightsPickDemo.module.css'

const ROW_HEIGHT = 46

function Crown() {
  return (
    <svg viewBox="0 0 24 20" width="18" height="15" aria-hidden="true">
      <path d="M2 17 4 5l5 5 3-8 3 8 5-5 2 12z" fill="currentColor" />
    </svg>
  )
}

function Pips({ votes }: { votes: number }) {
  return (
    <span className={classes.pips} aria-label={`${votes} of ${HEADCOUNT} votes`}>
      {Array.from({ length: HEADCOUNT }, (_, i) => (
        <span key={i} className={classes.pip} data-on={i < votes || undefined} />
      ))}
    </span>
  )
}

function Table({ game }: { game: Game }) {
  const seated = game.phase === 'rsvp' ? game.n : HEADCOUNT
  const winner = game.phase === 'pick' ? game.rows[ranking(game.rows)[0]] : undefined
  return (
    <div className={classes.table}>
      <div className={classes.felt}>
        {winner ? (
          <>
            <span className={classes.feltSmall}>Tonight</span>
            <span className={classes.feltWinner}>{winner.name}</span>
          </>
        ) : (
          <>
            <span className={classes.feltBig}>{seated}</span>
            <span className={classes.feltSmall}>going</span>
          </>
        )}
      </div>
      {PLAYERS.map((p, i) => {
        const angle = (-90 + (360 / HEADCOUNT) * i) * (Math.PI / 180)
        const style = {
          left: `calc(50% + ${Math.cos(angle) * 41}% - 22px)`,
          top: `calc(50% + ${Math.sin(angle) * 41}% - 26px)`,
        } as CSSProperties
        return (
          <div
            key={p.name}
            className={classes.seat}
            style={style}
            data-seated={i < seated || undefined}
          >
            <Meeple color={p.color} outline={palette.olive} width={44} height={44} />
            <span className={classes.seatName}>{p.name}</span>
          </div>
        )
      })}
    </div>
  )
}

function Shelf({ game }: { game: Game }) {
  const { phase, n, rows } = game
  const shown = phase === 'rsvp' ? 0 : phase === 'pool' ? n : rows.length
  const checked = phase === 'fit' ? n : phase === 'vote' || phase === 'pick' ? rows.length : 0
  const ranked = phase === 'vote' || phase === 'pick'
  const order = ranking(rows)

  return (
    <div
      className={classes.shelf}
      style={{ height: (ranked ? order.length : rows.length) * ROW_HEIGHT }}
    >
      {rows.map((row, i) => {
        const rank = order.indexOf(i)
        const slot = ranked && row.fits ? rank : i
        const verdict = i < checked ? (row.fits ? 'fits' : 'out') : undefined
        const winner = phase === 'pick' && rank === 0
        return (
          <div
            key={`${game.round}-${row.name}`}
            className={classes.row}
            style={{ transform: `translateY(${slot * ROW_HEIGHT}px)` }}
            data-shown={i < shown || undefined}
            data-verdict={verdict}
            data-gone={(ranked && !row.fits) || undefined}
            data-winner={winner || undefined}
          >
            <Meeple
              color={PLAYERS[row.owner].color}
              outline={palette.olive}
              width={20}
              height={20}
              className={classes.owner}
            />
            <span className={classes.name}>{row.name}</span>
            <span className={classes.range}>
              {row.min === row.max ? row.min : `${row.min}–${row.max}`}
            </span>
            <span className={classes.status}>
              {winner ? (
                <span className={classes.crown}>
                  <Crown /> Pick
                </span>
              ) : ranked ? (
                <Pips votes={row.votes} />
              ) : verdict === 'fits' ? (
                <span className={classes.fits}>✓ fits</span>
              ) : verdict === 'out' ? (
                <span className={classes.out}>
                  ✗ {row.max < HEADCOUNT ? `max ${row.max}` : `min ${row.min}`}
                </span>
              ) : null}
            </span>
          </div>
        )
      })}
    </div>
  )
}

/** The landing page's live demo of a meetup coming together. */
export function TonightsPickDemo() {
  // Without motion (or something to watch scrolling with), show the finished pick and hold.
  const [animated] = useState(
    () => typeof IntersectionObserver !== 'undefined' && !prefersReducedMotion(),
  )
  const [game, setGame] = useState<Game>(() => {
    const rows = dealRound()
    return animated
      ? { round: 1, rows, phase: 'rsvp', n: 0 }
      : { round: 1, rows, phase: 'pick', n: 0 }
  })
  const { ref, inView } = useInView<HTMLDivElement>(0.3)
  const running = animated && inView

  useEffect(() => {
    if (!running) return
    const [next, delay] = nextGame(game)
    const timer = setTimeout(() => setGame(next), delay)
    return () => clearTimeout(timer)
  }, [running, game])

  return (
    <div ref={ref} className={classes.stage}>
      <div className={classes.bar}>
        <span className={classes.round} data-testid="demo-round">
          Round {game.round} · {LABELS[game.phase]}
        </span>
        <span className={classes.live}>
          <span className={classes.liveDot} />
          Demo
        </span>
      </div>
      <div className={classes.body}>
        <Table game={game} />
        <div className={classes.side}>
          <Shelf game={game} />
          <div className={classes.dieSlot} data-shown={game.phase === 'pick' || undefined}>
            <Die size={30} rollKey={game.phase === 'pick' ? game.round : undefined} />
            <span>Who goes first? Roll for it.</span>
          </div>
        </div>
      </div>
    </div>
  )
}
