import type { SVGProps } from 'react'

/** The meeple silhouette path, drawn in a 100 × 100 box. */
export const MEEPLE_PATH =
  'M50 6c-10.5 0-16.5 8-16.5 17 0 5 1.6 8.6 3.4 11C24 38.4 9 44 6.5 53.5 5 59.8 11.5 63 21 63.5 17 73 11.5 84 9 94h29c3-7.5 7-13.5 12-13.5S59 86.5 62 94h29c-2.5-10-8-21-12-30.5 9.5-.5 16-3.7 14.5-10C91 44 76 38.4 63.1 34c1.8-2.4 3.4-6 3.4-11C66.5 14 60.5 6 50 6z'

type MeepleProps = SVGProps<SVGSVGElement> & { color: string; outline?: string }

/** A single meeple, sized by width/height like any SVG. */
export function Meeple({ color, outline, ...props }: MeepleProps) {
  return (
    <svg viewBox="0 0 100 100" aria-hidden="true" {...props}>
      <path
        d={MEEPLE_PATH}
        fill={color}
        stroke={outline}
        strokeWidth={outline ? 5 : 0}
        strokeLinejoin="round"
      />
    </svg>
  )
}
