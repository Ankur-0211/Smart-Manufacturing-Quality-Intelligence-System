import type { RouteObject } from 'react-router-dom'

import { AnalyticsScreen } from '@/features/analytics/AnalyticsScreen'
import { ExplainabilityScreen } from '@/features/explainability/ExplainabilityScreen'
import { ModelInfoScreen } from '@/features/model-info/ModelInfoScreen'
import { HistoryScreen } from '@/features/history/HistoryScreen'
import { RunDetailScreen } from '@/features/history/RunDetailScreen'
import { ProcessControlScreen } from '@/features/process-control/ProcessControlScreen'
import { RecommendationsScreen } from '@/features/recommendations/RecommendationsScreen'
import { CompareScreen } from '@/features/whatif/CompareScreen'
import { WhatIfScreen } from '@/features/whatif/WhatIfScreen'

import { AppShell } from './AppShell'
import { ScreenPlaceholder } from './ScreenPlaceholder'
import { SCREENS } from './screens'

const IMPLEMENTED: Record<string, RouteObject> = {
  '/': { index: true, element: <ProcessControlScreen /> },
  '/history': { path: '/history', element: <HistoryScreen /> },
  '/explainability': { path: '/explainability', element: <ExplainabilityScreen /> },
  '/what-if': { path: '/what-if', element: <WhatIfScreen /> },
  '/recommendations': { path: '/recommendations', element: <RecommendationsScreen /> },
  '/analytics': { path: '/analytics', element: <AnalyticsScreen /> },
  '/model-info': { path: '/model-info', element: <ModelInfoScreen /> },
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
      { path: '/what-if/compare', element: <CompareScreen /> },
    ],
  },
]
