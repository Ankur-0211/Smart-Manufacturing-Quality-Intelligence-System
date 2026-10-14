import { NavLink, Outlet } from 'react-router-dom'

import { ApiStatus, MockBanner, SimulationDisclaimer } from '@/components/common/Banners'
import { cn } from '@/lib/utils'

import { SCREENS } from './screens'

export function AppShell() {
  return (
    <div className="flex h-full flex-col">
      <MockBanner />
      <header className="flex items-center gap-6 border-b border-border bg-panel px-4 py-2">
        <h1 className="text-sm font-semibold tracking-widest text-text uppercase">
          Smart Manufacturing Quality Intelligence
        </h1>
        <nav aria-label="Screens" className="flex flex-1 flex-wrap gap-1">
          {SCREENS.map((s) => (
            <NavLink
              key={s.path}
              to={s.path}
              end={s.path === '/'}
              className={({ isActive }) =>
                cn(
                  'rounded px-2.5 py-1 text-sm text-text-muted hover:bg-panel-raised hover:text-text',
                  isActive && 'bg-panel-raised text-state-active',
                )
              }
            >
              {s.label}
            </NavLink>
          ))}
        </nav>
        <ApiStatus />
      </header>
      <main className="flex-1 overflow-auto p-4">
        <Outlet />
      </main>
      <SimulationDisclaimer />
    </div>
  )
}
