import type { RouteObject } from 'react-router-dom'

import { ProcessControlScreen } from '@/features/process-control/ProcessControlScreen'

import { AppShell } from './AppShell'
import { ScreenPlaceholder } from './ScreenPlaceholder'
import { SCREENS } from './screens'

export const routes: RouteObject[] = [
  {
    element: <AppShell />,
    children: SCREENS.map((screen) =>
      screen.path === '/'
        ? { index: true, element: <ProcessControlScreen /> }
        : { path: screen.path, element: <ScreenPlaceholder screen={screen} /> },
    ),
  },
]
