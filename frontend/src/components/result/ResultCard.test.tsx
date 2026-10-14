import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { prediction } from '@/test/fixtures/runEvents'

import { ResultCard } from './ResultCard'

describe('ResultCard', () => {
  it('waits for the quality stage without inventing numbers', () => {
    render(<ResultCard prediction={null} />)
    const card = screen.getByRole('region', { name: 'Quality result' })
    expect(card).toHaveTextContent('Awaiting the quality inspection stage.')
    expect(card.textContent).not.toMatch(/\d\.\d/)
  })

  it('keeps probability, operational risk and anomaly as three distinct blocks', () => {
    render(<ResultCard prediction={prediction()} />)
    const prob = screen.getByRole('region', { name: 'Model-predicted failure probability' })
    const risk = screen.getByRole('region', { name: 'Operational risk' })
    const anomaly = screen.getByRole('region', { name: 'Anomaly status' })
    expect(prob).toHaveTextContent('0.71')
    expect(prob).toHaveTextContent('(calibrated)')
    expect(prob).toHaveTextContent('Prediction: FAIL')
    expect(prob).toHaveTextContent('threshold 0.42')
    expect(within(risk).getByText('HIGH')).toBeInTheDocument()
    expect(anomaly).toHaveTextContent('Not evaluated')
    expect(screen.getByText(/Risk origin:/)).toHaveTextContent('COOLING 58%')
  })

  it('shows NOT RELEASABLE for an overridden critical breach', () => {
    render(
      <ResultCard
        prediction={prediction({
          label: 'PASS',
          p_fail: 0.12,
          risk_level: 'CRITICAL',
          constraint_override_applied: true,
          caveats: [{ code: 'CRITICAL_CONSTRAINT_OVERRIDDEN', message: 'HC-001 overridden', features: [] }],
        })}
      />,
    )
    expect(screen.getByRole('alert')).toHaveTextContent('NOT RELEASABLE')
    expect(screen.getByRole('region', { name: 'Model-predicted failure probability' })).toHaveTextContent(
      'Model label: PASS',
    )
    expect(screen.queryByText('Prediction: PASS')).not.toBeInTheDocument()
    expect(screen.getByRole('list', { name: 'Caveats' })).toHaveTextContent('CRITICAL_CONSTRAINT_OVERRIDDEN')
  })

  it('labels mock output and reports anomaly and extrapolation', () => {
    render(
      <ResultCard
        prediction={prediction({
          is_mock: true,
          inference_backend: 'mock',
          anomaly_global: { is_anomaly: true, score: 0.9, note: 'unusual' },
          ood: { is_out_of_distribution: true, features_outside: [{ feature: 'melt_temp_c' }] },
        })}
      />,
    )
    expect(screen.getByText('MOCK OUTPUT')).toBeInTheDocument()
    const anomaly = screen.getByRole('region', { name: 'Anomaly status' })
    expect(anomaly).toHaveTextContent('Unusual process condition')
    expect(anomaly).toHaveTextContent('Outside training range on 1 feature(s)')
  })
})
