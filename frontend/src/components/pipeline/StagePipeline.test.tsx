import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { SimulationEvent } from '@/features/process-control/model'
import { initialRunState, runReducer, type RunViewState } from '@/features/process-control/runReducer'
import { fullRun, prediction, RUN_ID, StreamBuilder } from '@/test/fixtures/runEvents'

import { StagePipeline } from './StagePipeline'

function stateFrom(events: SimulationEvent[]): RunViewState {
  return events.reduce((s, event) => runReducer(s, { kind: 'event', event }), initialRunState(RUN_ID))
}

function node(name: RegExp): HTMLElement {
  return screen.getByRole('listitem', { name })
}

describe('StagePipeline', () => {
  it('renders six stages, all pending, when idle', () => {
    const s = initialRunState()
    render(<StagePipeline stages={s.stages} prediction={null} />)
    const items = within(screen.getByRole('list', { name: 'Process stages' })).getAllByRole('listitem')
    expect(items).toHaveLength(6)
    for (const item of items) {
      expect(item).toHaveAttribute('data-state', 'PENDING')
      expect(item).toHaveTextContent('[ ]')
      expect(item).toHaveTextContent('PENDING')
    }
  })

  it('pairs every completed state with a glyph and a text label, not colour only', () => {
    const s = stateFrom(fullRun())
    render(<StagePipeline stages={s.stages} prediction={s.prediction} />)
    const cooling = node(/Cooling \/ Ejection: completed, health 0.41, risk HIGH/)
    expect(cooling).toHaveTextContent('[X]')
    expect(cooling).toHaveTextContent('HIGH')
    expect(cooling).toHaveTextContent('0.41')
    expect(node(/Plasticizing \/ Thermal: .*anomaly flagged/)).toHaveTextContent('!')
    expect(node(/Quality Inspection \/ Fusion: FAIL, predicted failure probability 0.71/)).toHaveTextContent(
      'FAIL',
    )
  })

  it('shows the active stage', () => {
    const s = stateFrom(new StreamBuilder().push('run.started').push('stage.started', 'INJECTION').events)
    render(<StagePipeline stages={s.stages} prediction={null} />)
    expect(node(/Injection \/ Fill: active/)).toHaveTextContent('[*]')
  })

  it('shows BLOCKED with its own glyph', () => {
    const s = stateFrom(
      new StreamBuilder()
        .push('run.started')
        .push('stage.started', 'PLASTICIZING')
        .push('stage.blocked', 'PLASTICIZING', {
          reason: 'ceiling',
        }).events,
    )
    render(<StagePipeline stages={s.stages} prediction={null} />)
    const blocked = node(/Plasticizing \/ Thermal: blocked/)
    expect(blocked).toHaveTextContent('[/]')
    expect(blocked).toHaveTextContent('BLOCKED')
  })

  it('never shows an overridden critical breach as a plain PASS', () => {
    const s = stateFrom(
      fullRun(prediction({ label: 'PASS', p_fail: 0.1, constraint_override_applied: true })),
    )
    render(<StagePipeline stages={s.stages} prediction={s.prediction} />)
    const quality = node(/Quality Inspection \/ Fusion: NOT RELEASABLE/)
    expect(quality).toHaveTextContent('NOT REL.')
    expect(quality).not.toHaveTextContent(/\bPASS\b/)
  })

  it('reports stage selection', async () => {
    const onSelect = vi.fn()
    const s = initialRunState()
    render(<StagePipeline stages={s.stages} prediction={null} onSelectStage={onSelect} />)
    await userEvent.click(node(/Packing \/ Holding/))
    expect(onSelect).toHaveBeenCalledWith('PACKING')
  })
})
