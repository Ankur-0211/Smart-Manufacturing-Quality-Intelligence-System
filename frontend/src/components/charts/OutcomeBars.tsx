import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

export interface OutcomeBar {
  label: string
  rate: number | null // model-predicted FAIL share; null when no run in the group has a prediction
  runs: number
}

/**
 * Predicted FAIL share per group (roadmap R2-P8 task 4). Groups without a prediction draw no bar.
 * Decorative for assistive technology; the caller renders the same numbers as a table.
 */
export function OutcomeBars({ bars, height = 200 }: { bars: OutcomeBar[]; height?: number }) {
  const data = bars.map((b) => ({ ...b, value: b.rate ?? 0 }))
  return (
    <div aria-hidden="true" style={{ height }} className="w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 8, bottom: 4, left: 0 }}>
          <CartesianGrid stroke="var(--color-border)" strokeDasharray="2 4" vertical={false} />
          <XAxis dataKey="label" stroke="var(--color-text-muted)" fontSize={11} interval={0} />
          <YAxis
            domain={[0, 1]}
            stroke="var(--color-text-muted)"
            fontSize={11}
            width={36}
            tickFormatter={(v: number) => `${Math.round(v * 100)}%`}
          />
          <Tooltip
            cursor={{ fill: 'var(--color-panel-raised)' }}
            contentStyle={{
              background: 'var(--color-panel)',
              border: '1px solid var(--color-border)',
              fontSize: 12,
            }}
            formatter={(v, _name, item) => [
              `${Math.round(Number(v) * 100)} % of ${(item.payload as OutcomeBar).runs} runs`,
              'predicted FAIL',
            ]}
          />
          <Bar dataKey="value" fill="var(--color-risk-high)" maxBarSize={56} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
