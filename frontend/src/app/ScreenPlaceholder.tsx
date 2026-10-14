import type { ScreenDef } from './screens'

/** Stub used until each screen is implemented in its roadmap phase. Shows no data. */
export function ScreenPlaceholder({ screen }: { screen: ScreenDef }) {
  return (
    <section aria-labelledby="screen-title" className="max-w-3xl rounded border border-border bg-panel p-6">
      <h2 id="screen-title" className="text-lg font-semibold">
        {screen.label}
      </h2>
      <p className="mt-2 text-text-muted">{screen.purpose}</p>
      <p className="mt-4 text-sm text-text-muted">
        Not implemented yet — scheduled for roadmap phase <span className="numeric">{screen.phase}</span>.
      </p>
    </section>
  )
}
