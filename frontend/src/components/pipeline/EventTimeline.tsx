import type { TimelineEntry, TimelineTone } from '@/features/process-control/runReducer'
import { cn } from '@/lib/utils'

const TONE: Record<TimelineTone, string> = {
  info: 'text-text-muted',
  success: 'text-risk-normal',
  warning: 'text-risk-medium',
  critical: 'text-risk-critical',
  anomaly: 'text-anomaly',
}

function clock(ts: string): string {
  const d = new Date(ts)
  return Number.isNaN(d.getTime()) ? ts : d.toISOString().slice(11, 19)
}

/** Live event log (Plan F9). Newest entries at the bottom, announced politely to screen readers. */
export function EventTimeline({ entries }: { entries: TimelineEntry[] }) {
  return (
    <section aria-labelledby="timeline-title" className="flex min-h-0 flex-col">
      <h3
        id="timeline-title"
        className="mb-2 text-xs font-semibold tracking-widest text-text-muted uppercase"
      >
        Event timeline
      </h3>
      {entries.length === 0 ? (
        <p className="text-sm text-text-muted">No events yet. Start a run to see stage events here.</p>
      ) : (
        <ol aria-live="polite" className="numeric max-h-72 space-y-0.5 overflow-auto text-xs">
          {entries.map((e) => (
            <li key={e.seq} className="flex gap-3" data-tone={e.tone}>
              <span className="w-16 shrink-0 text-text-muted">{clock(e.ts)}</span>
              <span className={cn('shrink-0', TONE[e.tone])}>{e.tone === 'anomaly' ? '!' : '·'}</span>
              <span className={TONE[e.tone]}>{e.summary}</span>
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}
