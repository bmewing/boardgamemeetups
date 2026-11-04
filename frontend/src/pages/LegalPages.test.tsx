import { screen } from '@testing-library/react'
import { Route, Routes } from 'react-router'
import { describe, expect, it } from 'vitest'

import { renderWithProviders } from '../test/render'
import { PrivacyPage, TermsPage } from './LegalPages'

function renderAt(route: string) {
  renderWithProviders(
    <Routes>
      <Route path="/terms" element={<TermsPage />} />
      <Route path="/privacy" element={<PrivacyPage />} />
    </Routes>,
    { route },
  )
}

describe('LegalPages', () => {
  it('shows the terms to anyone, signed in or not', () => {
    renderAt('/terms')

    expect(screen.getByRole('heading', { name: 'Terms of service' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'privacy policy' })).toHaveAttribute('href', '/privacy')
  })

  it('says how to delete your data, at a link that can be shared', () => {
    renderAt('/privacy')

    expect(screen.getByRole('heading', { name: 'Privacy policy' })).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: 'Deleting your data' }).parentElement,
    ).toHaveAttribute('id', 'delete')
    expect(screen.getAllByRole('link', { name: 'admin@bggroup.app' })[0]).toHaveAttribute(
      'href',
      'mailto:admin@bggroup.app',
    )
  })
})
