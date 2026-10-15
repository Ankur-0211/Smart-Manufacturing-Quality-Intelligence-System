import type { RouteObject } from 'react-router-dom'

import { HistoryScreen } from '@/features/history/HistoryScreen'
import { RunDetailScreen } from '@/features/history/RunDetailScreen'
import { ProcessControlScreen } from '@/features/process-control/ProcessControlScreen'

import { AppShell } from './AppShell'
import { ScreenPlaceholder } from './ScreenPlaceholder'
import { SCREENS } from './screens'

const IMPLEMENTED: Record<string, RouteObject> = {
  '/': { index: true, element: <ProcessControlScreen /> },
  '/history': { path: '/history', element: <HistoryScreen /> },
}

export const routes: RouteObject[] = [
  {
    element: <AppShell />,
    children: [
      ...SCREENS.map(
        (screen) =>
          IMPLEMENTED[screen.path] ?? { path: screen.path, element: <ScreenPlaceholder screen={screen} /> },
      ),
      { path: '/history/:runId', element: <RunDetailScreen /> },
    ],
  },
]
