import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

export interface SeriesPoint {
  x: string
  y: number
}

/**
 * A plain stored-value series (runs over time, the SPC parameter series). No control limits are
 * drawn: those come only from the intelligence layer's SPC check (roadmap R2-P8 §15).
 * Decorative for assistive technology; the caller states the numbers.
 */
export function SeriesLine({
  points,
  name,
  height = 200,
}: {
  points: SeriesPoint[]
  name: string
  height?: number
}) {
  return (
    <div aria-hidden="true" style={{ height }} className="w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={points} margin={{ top: 8, right: 16, bottom: 4, left: 0 }}>
          <CartesianGrid stroke="var(--color-border)" strokeDasharray="2 4" />
          <XAxis dataKey="x" stroke="var(--color-text-muted)" fontSize={11} minTickGap={24} />
          <YAxis
            stroke="var(--color-text-muted)"
            fontSize={11}
            width={44}
            domain={['auto', 'auto']}
            allowDecimals
          />
          <Tooltip
            contentStyle={{
              background: 'var(--color-panel)',
              border: '1px solid var(--color-border)',
              fontSize: 12,
            }}
            formatter={(v) => [String(v), name]}
          />
          <Line
            type="linear"
            dataKey="y"
            stroke="var(--color-state-active)"
            strokeWidth={2}
            dot={{ r: 2 }}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
