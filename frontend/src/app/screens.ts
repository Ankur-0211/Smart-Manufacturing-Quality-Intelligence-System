/** The seven screens of the SPA (Plan 15.3). Process Control is the default. */
export interface ScreenDef {
  path: string
  label: string
  purpose: string
  phase: string
}

export const SCREENS: readonly ScreenDef[] = [
  {
    path: '/',
    label: 'Process Control',
    purpose: 'Run and watch a simulation through the six manufacturing stages.',
    phase: 'R2-P6',
  },
  {
    path: '/explainability',
    label: 'Explainability',
    purpose: 'Understand a prediction: SHAP attributions and stage risk mass.',
    phase: 'R2-P7',
  },
  {
    path: '/what-if',
    label: 'What-If',
    purpose: 'Mutate parameters and compare against the parent run.',
    phase: 'R2-P7',
  },
  {
    path: '/recommendations',
    label: 'Recommendations',
    purpose: 'Constrained, model-relative options for a failing recipe.',
    phase: 'R2-P7',
  },
  {
    path: '/history',
    label: 'History',
    purpose: 'Browse past runs, scenarios and what-if lineage.',
    phase: 'R2-P8',
  },
  {
    path: '/analytics',
    label: 'Analytics',
    purpose: 'Failure patterns across machines, lots, parameters and stages.',
    phase: 'R2-P8',
  },
  {
    path: '/model-info',
    label: 'Model Info',
    purpose: 'Active model version, training data provenance and evaluation metrics.',
    phase: 'R2-P7',
  },
]
