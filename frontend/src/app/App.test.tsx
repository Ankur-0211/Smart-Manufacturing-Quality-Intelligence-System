import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { DISCLAIMER_SIMULATION, MOCK_BANNER_TEXT } from '@/lib/disclaimers'
import { API, envelope, healthPayload, server } from '@/test/server'

import { App } from './App'
import { createQueryClient } from './queryClient'
import { SCREENS } from './screens'

function renderApp(path = '/') {
  return render(<App initialEntries={[path]} queryClient={createQueryClient()} />)
}

describe('App shell', () => {
  it('lists all seven screens with Process Control as the default', async () => {
    renderApp()
    const nav = screen.getByRole('navigation', { name: 'Screens' })
    const links = within(nav).getAllByRole('link')
    expect(links.map((l) => l.textContent)).toEqual(SCREENS.map((s) => s.label))
    expect(SCREENS).toHaveLength(7)
    expect(await screen.findByRole('heading', { name: 'Process Control' })).toBeInTheDocument()
  })

  it('navigates between screens', async () => {
    renderApp()
    await userEvent.click(screen.getByRole('link', { name: 'What-If' }))
    expect(await screen.findByRole('heading', { name: 'What-If' })).toBeInTheDocument()
  })

  it('always shows the software-simulation disclaimer', () => {
    renderApp('/analytics')
    expect(screen.getByText(DISCLAIMER_SIMULATION)).toBeInTheDocument()
  })

  it('shows the MOCK banner when the backend runs mock intelligence', async () => {
    renderApp()
    expect(await screen.findByRole('alert')).toHaveTextContent(MOCK_BANNER_TEXT)
  })

  it('hides the MOCK banner only for real intelligence', async () => {
    server.use(
      http.get(`${API}/health`, () =>
        HttpResponse.json(envelope(healthPayload({ status: 'ok', intelligence_backend: 'real' }))),
      ),
    )
    renderApp()
    expect(await screen.findByText('API: ok')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('shows the banner for hybrid intelligence too', async () => {
    server.use(
      http.get(`${API}/health`, () =>
        HttpResponse.json(envelope(healthPayload({ intelligence_backend: 'hybrid' }))),
      ),
    )
    renderApp()
    expect(await screen.findByRole('alert')).toHaveTextContent('hybrid')
  })
})
