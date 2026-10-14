import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { App } from '@/app/App'
import { createQueryClient } from '@/app/queryClient'

describe('ProcessControlScreen (idle, before the simulation API exists)', () => {
  it('shows an idle pipeline and no fabricated results', async () => {
    render(<App initialEntries={['/']} queryClient={createQueryClient()} />)
    const pipeline = await screen.findByRole('list', { name: 'Process stages' })
    const nodes = within(pipeline).getAllByRole('listitem')
    expect(nodes).toHaveLength(6)
    expect(nodes.every((n) => n.getAttribute('data-state') === 'PENDING')).toBe(true)
    expect(screen.getByRole('region', { name: 'Quality result' })).toHaveTextContent(
      'Awaiting the quality inspection stage.',
    )
    expect(screen.getByText('No events yet. Start a run to see stage events here.')).toBeInTheDocument()
  })

  it('disables run controls until the simulation API is wired', async () => {
    render(<App initialEntries={['/']} queryClient={createQueryClient()} />)
    const controls = await screen.findByRole('group', { name: 'Run controls' })
    for (const button of within(controls).getAllByRole('button')) expect(button).toBeDisabled()
    expect(controls).toHaveTextContent('simulation API in R2-P4')
    expect(within(controls).getByLabelText('Presentation speed')).toBeDisabled()
  })
})
