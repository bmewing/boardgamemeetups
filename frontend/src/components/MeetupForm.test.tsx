import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { renderWithProviders } from '../test/render'
import { type MeetupFields, MeetupForm } from './MeetupForm'

const initial: MeetupFields = {
  local_date: '2099-01-01',
  local_time: '19:00',
  duration_minutes: 180,
  location: "Sam's place",
  is_online: false,
  online_url: '',
  notes: '',
}

describe('MeetupForm', () => {
  it('swaps the place for a table link when the date is online', async () => {
    const sent: MeetupFields[] = []
    renderWithProviders(
      <MeetupForm
        initial={initial}
        submitLabel="Add"
        busy={false}
        onSubmit={(f) => sent.push(f)}
      />,
    )
    expect(screen.getByLabelText('Place')).toHaveValue("Sam's place")

    await userEvent.click(screen.getByRole('switch', { name: /Online on Board Game Arena/ }))
    expect(screen.queryByLabelText('Place')).not.toBeInTheDocument()
    await userEvent.type(
      screen.getByRole('textbox', { name: /Table link/ }),
      'https://boardgamearena.com/table?table=7',
    )
    await userEvent.click(screen.getByRole('button', { name: 'Add' }))

    expect(sent).toEqual([
      { ...initial, is_online: true, online_url: 'https://boardgamearena.com/table?table=7' },
    ])
  })
})
