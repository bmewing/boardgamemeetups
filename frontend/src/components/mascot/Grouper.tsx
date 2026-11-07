import type { CSSProperties } from 'react'

import './Grouper.css'

export type GrouperPose =
  | 'idle'
  | 'toss'
  | 'twirl'
  | 'wave'
  | 'think'
  | 'snooze'
  | 'cheer'
  | 'deal'
  | 'oops'
  | 'winner'
  | 'shuffle'
  | 'head'

// The grouper is Greg, as in Good Guy Greg.
const LABELS: Record<GrouperPose, string> = {
  idle: 'Greg the grouper, smiling',
  toss: 'Greg the grouper tossing a die',
  twirl: 'Greg the grouper spinning a meeple on his fin',
  wave: 'Greg the grouper waving hello',
  think: 'Greg the grouper thinking',
  snooze: 'Greg the grouper fast asleep',
  cheer: 'Greg the grouper celebrating',
  deal: 'Greg the grouper holding a fan of cards',
  oops: 'Greg the grouper looking sheepish beside spilled dice',
  winner: 'Greg the grouper proudly holding a trophy',
  shuffle: 'Greg the grouper shuffling cards',
  head: 'Greg the grouper, smiling',
}

type GrouperProps = {
  pose?: GrouperPose
  /** Width and height in px. */
  size?: number
  /** Pass an empty label for a decorative image. */
  label?: string
  className?: string
  style?: CSSProperties
  /** Use a still illustration, for example next to a long block of text. */
  animated?: boolean
}

/** Greg, the site's grouper: generated character artwork with layered motion; respects reduced-motion preferences. */
export function Grouper({
  pose = 'idle',
  size = 160,
  label,
  className,
  style,
  animated = true,
}: GrouperProps) {
  const base = `${import.meta.env.BASE_URL}mascot/`
  const head = pose === 'head'
  return (
    <img
      src={`${base}grouper-${pose}.${animated && !head ? 'svg' : 'png'}`}
      srcSet={
        head
          ? `${[32, 48, 64, 128, 256].map((px) => `${base}grouper-head-${px}.png ${px}w`).join(', ')}, ${base}grouper-head.png 512w`
          : undefined
      }
      sizes={head ? `${size}px` : undefined}
      alt={label ?? LABELS[pose]}
      width={size}
      height={size}
      className={className ? `grp ${className}` : 'grp'}
      style={style}
      data-pose={pose}
      decoding="async"
      draggable={false}
    />
  )
}
