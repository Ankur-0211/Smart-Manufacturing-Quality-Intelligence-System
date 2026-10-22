import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { App } from '@/app/App'
import { createQueryClient } from '@/app/queryClient'
import { FakeEventSource } from '@/test/fakeEventSource'
import { materials } from '@/test/fixtures/reference'
import { API, envelope, server } from '@/test/server'

function renderApp() {
  return render(
    <App
      initialEntries={['/']}
      queryClient={createQueryClient()}
      eventSourceFactory={(u) => new FakeEventSource(u)}
    />,
  )
}

async function openDialog(user: ReturnType<typeof userEvent.setup>) {
  const panel = await screen.findByRole('region', { name: 'Parameter panel' })
  await user.click(await within(panel).findByRole('button', { name: 'New lot…' }))
  return screen.getByRole('dialog', { name: 'Create material lot' })
}

async function fill(user: ReturnType<typeof userEvent.setup>, dialog: HTMLElement, code = 'E-200') {
  await user.type(within(dialog).getByLabelText('Lot code'), code)
  await user.selectOptions(within(dialog).getByLabelText('Resin grade'), 'PP-C')
  await user.type(within(dialog).getByLabelText('MFI (g/10 min)'), '15')
  await user.type(within(dialog).getByLabelText('Moisture (%)'), '0.03')
  await user.type(within(dialog).getByLabelText('Regrind (%)'), '5')
  await user.type(within(dialog).getByLabelText('Colourant (%)'), '1')
}

describe('Create lot dialog', () => {
  it('creates a lot through the API and selects it', async () => {
    const user = userEvent.setup()
    let body: unknown = null
    let created = false
    server.use(
      http.post(`${API}/materials`, async ({ request }) => {
        body = await request.json()
        created = true
        return HttpResponse.json(
          envelope({ material_lot_id: 'E-200', resin_grade: 'PP-C', moisture_pct: 0.03 }),
          { status: 201 },
        )
      }),
      http.get(`${API}/materials`, () =>
        HttpResponse.json(
          envelope(
            created
              ? [...materials, { material_lot_id: 'E-200', resin_grade: 'PP-C', moisture_pct: 0.03 }]
              : materials,
          ),
        ),
      ),
    )
    renderApp()
    const dialog = await openDialog(user)
    expect(within(dialog).getByRole('button', { name: 'Create lot' })).toBeDisabled() // incomplete
    await fill(user, dialog)
    await user.click(within(dialog).getByRole('button', { name: 'Create lot' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(body).toEqual({
      material_lot_id: 'E-200',
      resin_grade: 'PP-C',
      mfi: 15,
      moisture_pct: 0.03,
      regrind_pct: 5,
      colourant_pct: 1,
      notes: null,
    })
    const panel = screen.getByRole('region', { name: 'Parameter panel' })
    await waitFor(() => expect(within(panel).getByLabelText('Material lot')).toHaveValue('E-200'))
  })

  it('shows the server answer on the right field (duplicate code, 409)', async () => {
    const user = userEvent.setup()
    server.use(
      http.post(`${API}/materials`, () =>
        HttpResponse.json(
          {
            data: null,
            error: {
              code: 'VALIDATION_ERROR',
              message: "material lot 'A-771' already exists",
              field: 'material_lot_id',
              hint: 'Lot codes are unique; choose another code.',
            },
            meta: { request_id: 'req-409' },
          },
          { status: 409 },
        ),
      ),
    )
    renderApp()
    const dialog = await openDialog(user)
    await fill(user, dialog, 'A-771')
    await user.click(within(dialog).getByRole('button', { name: 'Create lot' }))
    const code = within(dialog).getByLabelText('Lot code')
    await waitFor(() => expect(code).toHaveAttribute('aria-invalid', 'true'))
    expect(dialog).toHaveTextContent("material lot 'A-771' already exists")
    expect(screen.getByRole('dialog')).toBeInTheDocument() // stays open to correct
  })

  it('maps per-field 422 details', async () => {
    const user = userEvent.setup()
    server.use(
      http.post(`${API}/materials`, () =>
        HttpResponse.json(
          {
            data: null,
            error: {
              code: 'VALIDATION_ERROR',
              message: 'mfi: Input should be a valid number',
              field: 'mfi',
              details: [
                { field: 'mfi', code: 'VALIDATION_ERROR', message: 'Input should be a valid number' },
              ],
            },
            meta: { request_id: 'req-422' },
          },
          { status: 422 },
        ),
      ),
    )
    renderApp()
    const dialog = await openDialog(user)
    await fill(user, dialog)
    await user.click(within(dialog).getByRole('button', { name: 'Create lot' }))
    await waitFor(() =>
      expect(within(dialog).getByLabelText('MFI (g/10 min)')).toHaveAttribute('aria-invalid', 'true'),
    )
  })

  it('closes on Cancel and Escape without creating anything', async () => {
    const user = userEvent.setup()
    renderApp()
    const dialog = await openDialog(user)
    await user.click(within(dialog).getByRole('button', { name: 'Cancel' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    await openDialog(user)
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})
