import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'

import { STAGE_META, STAGE_ORDER, type StageName } from '@/features/process-control/model'

import { STAGE_COLOURS } from './stageColours'

export interface StageShare {
  stage: StageName
  share: number
}

/**
 * Stage risk mass donut (Plan §11.2): which stage's inputs carry the model's attribution.
 * Decorative for assistive technology; the caller renders the shares as a list.
 */
export function StageRiskDonut({ shares }: { shares: StageShare[] }) {
  const data = STAGE_ORDER.map((stage) => ({
    stage,
    name: STAGE_META[stage].short,
    value: shares.find((s) => s.stage === stage)?.share ?? 0,
  })).filter((d) => d.value > 0)
  return (
    <div aria-hidden="true" className="h-48 w-48">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            dataKey="value"
            nameKey="name"
            innerRadius="55%"
            outerRadius="90%"
            stroke="var(--color-panel)"
            isAnimationActive={false}
          >
            {data.map((d) => (
              <Cell key={d.stage} fill={STAGE_COLOURS[d.stage]} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{
              background: 'var(--color-panel)',
              border: '1px solid var(--color-border)',
              fontSize: 12,
            }}
            formatter={(v) => [`${Math.round(Number(v) * 100)} %`, 'share']}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  )
}
