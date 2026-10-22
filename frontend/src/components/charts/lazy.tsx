/**
 * Code-split chart components (roadmap R2-P9 task 5). Recharts is most of the bundle and only
 * these charts use it, so it loads on the first screen that draws one. Each wrapper reserves the
 * chart's height while loading; the charts are decorative (aria-hidden) and every screen shows
 * the same numbers as text, so nothing readable waits on the chunk.
 */
import { lazy, Suspense, type ComponentProps, type ComponentType } from 'react'

function split<P extends object>(
  load: () => Promise<ComponentType<P>>,
  height: (props: P) => number,
): ComponentType<P> {
  const Chart = lazy(async () => ({ default: await load() })) as unknown as ComponentType<P>
  function SplitChart(props: P) {
    return (
      <Suspense fallback={<div aria-hidden="true" className="w-full" style={{ height: height(props) }} />}>
        <Chart {...props} />
      </Suspense>
    )
  }
  return SplitChart
}

type ShapBarsProps = ComponentProps<typeof import('./ShapBars').ShapBars>
type HeightProps = { height?: number }

export const ShapBars = split<ShapBarsProps>(
  async () => (await import('./ShapBars')).ShapBars,
  (p) => Math.max(120, p.bars.length * 28 + 40),
)
export const StageRiskDonut = split<ComponentProps<typeof import('./StageRiskDonut').StageRiskDonut>>(
  async () => (await import('./StageRiskDonut')).StageRiskDonut,
  () => 192,
)
export const SensitivityCurve = split<ComponentProps<typeof import('./SensitivityCurve').SensitivityCurve>>(
  async () => (await import('./SensitivityCurve')).SensitivityCurve,
  () => 224,
)
export const OutcomeBars = split<ComponentProps<typeof import('./OutcomeBars').OutcomeBars> & HeightProps>(
  async () => (await import('./OutcomeBars')).OutcomeBars,
  (p) => p.height ?? 200,
)
export const SeriesLine = split<ComponentProps<typeof import('./SeriesLine').SeriesLine> & HeightProps>(
  async () => (await import('./SeriesLine')).SeriesLine,
  (p) => p.height ?? 200,
)
