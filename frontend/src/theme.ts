import {
  Button,
  Card,
  createTheme,
  type CSSVariablesResolver,
  type MantineColorsTuple,
} from '@mantine/core'

// The palette comes from the favicon: teal, cream, coral, navy and an olive ink line.
export const palette = {
  teal: '#1d7874',
  cream: '#ffeedb',
  coral: '#dd7373',
  navy: '#2b2d42',
  olive: '#514b23',
} as const

const meeple: MantineColorsTuple = [
  '#e6f4f3',
  '#c8e6e4',
  '#9dd2ce',
  '#6fbcb7',
  '#47a6a0',
  '#2a8f89',
  '#1d7874',
  '#17625f',
  '#114c4a',
  '#0b3735',
]

const coral: MantineColorsTuple = [
  '#fdf0f0',
  '#f9dcdc',
  '#f2bdbd',
  '#ea9c9c',
  '#e48585',
  '#dd7373',
  '#c95f5f',
  '#a94a4a',
  '#853a3a',
  '#622a2a',
]

const navy: MantineColorsTuple = [
  '#eeeff5',
  '#d6d8e4',
  '#b3b6ca',
  '#8d91ac',
  '#6b6f8d',
  '#525673',
  '#40435d',
  '#34364e',
  '#2b2d42',
  '#1f2031',
]

const olive: MantineColorsTuple = [
  '#f7f5e8',
  '#ebe7cb',
  '#d8d1a1',
  '#bfb672',
  '#a39a4f',
  '#857d3a',
  '#6d662e',
  '#5d5728',
  '#514b23',
  '#3a3518',
]

// Mantine's dark mode reads its surfaces from `dark`: tint it navy so dark mode is game night,
// not generic gray. 0 is the text color, 7 the page.
const dark: MantineColorsTuple = [
  '#f3e9dc',
  '#cdc5ba',
  '#9d9bac',
  '#73758c',
  '#53556e',
  '#424460',
  '#363851',
  '#2b2d42',
  '#222336',
  '#18192a',
]

export const theme = createTheme({
  primaryColor: 'meeple',
  primaryShade: { light: 6, dark: 5 },
  colors: { meeple, coral, navy, olive, dark },
  fontFamily: "'Nunito Variable', system-ui, -apple-system, 'Segoe UI', sans-serif",
  headings: {
    fontFamily: "'Fredoka Variable', 'Nunito Variable', system-ui, sans-serif",
    fontWeight: '600',
  },
  defaultRadius: 'md',
  // Hard offset shadows, like game pieces on a table. The ink color flips with the scheme.
  shadows: {
    xs: '2px 2px 0 var(--bgg-ink-soft)',
    sm: '3px 3px 0 var(--bgg-ink-soft)',
    md: '4px 4px 0 var(--bgg-ink)',
    lg: '6px 6px 0 var(--bgg-ink)',
    xl: '8px 8px 0 var(--bgg-ink)',
  },
  components: {
    Card: Card.extend({ defaultProps: { radius: 'lg', shadow: 'xs' } }),
    Button: Button.extend({ classNames: { root: 'bgg-button' } }),
  },
})

export const cssVariablesResolver: CSSVariablesResolver = () => ({
  variables: {
    '--bgg-cream': palette.cream,
    '--bgg-teal': palette.teal,
    '--bgg-coral': palette.coral,
    '--bgg-navy': palette.navy,
    '--bgg-olive': palette.olive,
    '--bgg-font-display': "'Fredoka Variable', 'Nunito Variable', system-ui, sans-serif",
  },
  light: {
    '--mantine-color-body': '#fff7ee',
    '--mantine-color-default-border': '#e3d5bf',
    '--bgg-ink': palette.olive,
    '--bgg-ink-soft': 'rgba(81, 75, 35, 0.22)',
    '--bgg-surface': '#ffffff',
    '--bgg-band': palette.cream,
    '--bgg-hex-line': 'rgba(29, 120, 116, 0.09)',
    '--bgg-heading': palette.navy,
  },
  dark: {
    '--mantine-color-body': palette.navy,
    '--mantine-color-default-border': '#45475f',
    '--bgg-ink': '#121322',
    '--bgg-ink-soft': 'rgba(10, 11, 22, 0.55)',
    '--bgg-surface': '#33354b',
    '--bgg-band': '#25263a',
    '--bgg-hex-line': 'rgba(255, 238, 219, 0.05)',
    '--bgg-heading': palette.cream,
  },
})
