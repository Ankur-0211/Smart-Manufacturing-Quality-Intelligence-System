import { Bar, BarChart, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

export interface ShapBar {
  key: string
  label: string
  value: number
}

const TOWARD_FAIL = 'var(--color-risk-critical)'
const TOWARD_PASS = 'var(--color-risk-normal)'

/**
 * Signed horizontal SHAP bars (roadmap R2-P7 task 6): right = toward FAIL, left = toward PASS.
 * Decorative for assistive technology; the caller renders the same numbers as a table.
 */
export function ShapBars({ bars }: { bars: ShapBar[] }) {
  const height = Math.max(120, bars.length * 28 + 40)
  return (
    <div aria-hidden="true" style={{ height }} className="w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={bars} layout="vertical" margin={{ top: 4, right: 24, bottom: 4, left: 8 }}>
          <XAxis
            type="number"
            stroke="var(--color-text-muted)"
            fontSize={11}
            tickFormatter={(v: number) => v.toFixed(2)}
          />
          <YAxis
            type="category"
            dataKey="label"
            width={170}
            stroke="var(--color-text-muted)"
            fontSize={11}
            interval={0}
          />
          <ReferenceLine x={0} stroke="var(--color-border)" />
          <Tooltip
            cursor={{ fill: 'var(--color-panel-raised)' }}
            contentStyle={{
              background: 'var(--color-panel)',
              border: '1px solid var(--color-border)',
              fontSize: 12,
            }}
            formatter={(v) => [Number(v).toFixed(3), 'SHAP (log-odds)']}
          />
          <Bar dataKey="value" isAnimationActive={false}>
            {bars.map((b) => (
              <Cell key={b.key} fill={b.value >= 0 ? TOWARD_FAIL : TOWARD_PASS} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
