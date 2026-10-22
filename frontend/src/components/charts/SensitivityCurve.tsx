import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import type { SensitivityResult } from '@/api/whatif'

/**
 * One parameter's P(fail) curve across its admissible window (roadmap R2-P7 task 4): the current
 * value, the server's flip point and the decision threshold are reference lines. Decorative for
 * assistive technology; the caller states the same numbers as text.
 */
export function SensitivityCurve({
  result,
  threshold,
  unit,
}: {
  result: SensitivityResult
  threshold: number | null
  unit: string
}) {
  const points = result.points ?? []
  return (
    <div aria-hidden="true" className="h-56 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={points} margin={{ top: 16, right: 16, bottom: 4, left: 0 }}>
          <CartesianGrid stroke="var(--color-border)" strokeDasharray="2 4" />
          <XAxis
            type="number"
            dataKey="value"
            domain={['dataMin', 'dataMax']}
            stroke="var(--color-text-muted)"
            fontSize={11}
            tickFormatter={(v: number) => `${Number(v.toFixed(2))}`}
          />
          <YAxis
            domain={[0, 1]}
            stroke="var(--color-text-muted)"
            fontSize={11}
            width={36}
            tickFormatter={(v: number) => v.toFixed(1)}
          />
          {threshold != null && (
            <ReferenceLine
              y={threshold}
              stroke="var(--color-text-muted)"
              strokeDasharray="4 4"
              label={{
                value: 'threshold',
                fill: 'var(--color-text-muted)',
                fontSize: 10,
                position: 'insideBottomLeft',
              }}
            />
          )}
          <ReferenceLine
            x={result.current_value}
            stroke="var(--color-state-active)"
            label={{
              value: 'current',
              fill: 'var(--color-state-active)',
              fontSize: 10,
              position: 'insideTopRight',
            }}
          />
          {result.flip_point != null && (
            <ReferenceLine
              x={result.flip_point}
              stroke="var(--color-anomaly)"
              strokeDasharray="4 2"
              label={{ value: 'flip', fill: 'var(--color-anomaly)', fontSize: 10, position: 'insideTopLeft' }}
            />
          )}
          <Tooltip
            contentStyle={{
              background: 'var(--color-panel)',
              border: '1px solid var(--color-border)',
              fontSize: 12,
            }}
            labelFormatter={(v) => `${v} ${unit}`}
            formatter={(v) => [Number(v).toFixed(3), 'P(fail)']}
          />
          <Line
            type="monotone"
            dataKey="p_fail"
            stroke="var(--color-risk-critical)"
            strokeWidth={2}
            dot={{ r: 2 }}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
