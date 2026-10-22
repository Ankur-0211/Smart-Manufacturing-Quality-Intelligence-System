/**
 * Simulation run API hooks (roadmap §9.3.2). Types come from the generated OpenAPI schema.
 * Stage results / predictions are typed by the provisional view types until app.contracts lands.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiGet, apiPost, apiRequest, type Schemas } from './client'

export type ScenarioSummary = Schemas['ScenarioSummary']
export type SimulationState = Schemas['SimulationStateOut']
export type StartRequest = Schemas['StartRequest']
export type LineageNode = Schemas['LineageOut']
export type OverrideRequest = Schemas['OverrideRequest']

export interface RunFilters {
  machine_id?: string
  label?: 'PASS' | 'FAIL'
  risk_level?: 'NORMAL' | 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
  is_whatif?: boolean
  inference_backend?: 'real' | 'mock'
}

export function runsQueryString(filters: RunFilters, limit: number, offset: number): string {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== '') params.set(key, String(value))
  }
  params.set('limit', String(limit))
  params.set('offset', String(offset))
  return params.toString()
}

export function useRuns(filters: RunFilters, limit: number, offset: number) {
  return useQuery({
    queryKey: ['runs', filters, limit, offset],
    queryFn: async () => {
      const { data, meta } = await apiGet<ScenarioSummary[]>(
        `/simulation/runs?${runsQueryString(filters, limit, offset)}`,
      )
      return { rows: data, total: meta.total ?? data.length }
    },
    placeholderData: (previous) => previous,
  })
}

export function useRunState(runId: string | null) {
  return useQuery({
    queryKey: ['run', runId],
    queryFn: async () =>
      (await apiGet<SimulationState>(`/simulation/runs/${encodeURIComponent(runId!)}`)).data,
    enabled: Boolean(runId),
  })
}

/** Longest parent chain followed when looking for a lineage root (guards against bad data). */
const MAX_LINEAGE_DEPTH = 50

/**
 * The what-if lineage tree containing `runId` (roadmap R2-P8 task 2): follows parent_run_id up to
 * the root, then loads GET /simulation/runs/{root}/lineage so siblings and ancestors are shown.
 */
export function useLineage(runId: string | null) {
  return useQuery({
    queryKey: ['lineage', runId],
    queryFn: async () => {
      let rootId = runId!
      for (let depth = 0; depth < MAX_LINEAGE_DEPTH; depth += 1) {
        const run = (await apiGet<SimulationState>(`/simulation/runs/${encodeURIComponent(rootId)}`)).data
        if (!run.parent_run_id) break
        rootId = run.parent_run_id
      }
      const tree = (await apiGet<LineageNode>(`/simulation/runs/${encodeURIComponent(rootId)}/lineage`)).data
      return { rootId, tree }
    },
    enabled: Boolean(runId),
  })
}

export function useSetLabel(runId: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: async (label: string | null) =>
      (
        await apiRequest<ScenarioSummary>(`/simulation/runs/${encodeURIComponent(runId)}/label`, {
          method: 'PATCH',
          body: JSON.stringify({ scenario_label: label }),
        })
      ).data,
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['runs'] })
      void client.invalidateQueries({ queryKey: ['run', runId] })
      void client.invalidateQueries({ queryKey: ['lineage'] })
    },
  })
}

export type RunCommand =
  | { command: 'start'; body: StartRequest }
  | { command: 'advance' | 'pause' | 'resume' | 'reset' }
  | { command: 'abort'; body?: { reason?: string | null } }
  | { command: 'override'; body: OverrideRequest }

export function useRunCommand(runId: string | null) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: async (cmd: RunCommand) => {
      if (!runId) throw new Error('no run selected')
      const body = 'body' in cmd && cmd.body !== undefined ? JSON.stringify(cmd.body) : undefined
      return (
        await apiRequest<SimulationState>(`/simulation/runs/${encodeURIComponent(runId)}/${cmd.command}`, {
          method: 'POST',
          body,
        })
      ).data
    },
    onSettled: () => {
      void client.invalidateQueries({ queryKey: ['run', runId] })
      void client.invalidateQueries({ queryKey: ['runs'] })
    },
  })
}

export type CreateRunRequest = Schemas['CreateRunRequest']

/** POST /simulation/runs: the server validates the recipe against the registry (422 details). */
export function useCreateRun() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: async (body: CreateRunRequest) =>
      (await apiPost<SimulationState>('/simulation/runs', body)).data,
    onSuccess: (state) => {
      client.setQueryData(['run', state.run_id], state)
      void client.invalidateQueries({ queryKey: ['runs'] })
    },
  })
}

/** RUN for a new run: create it from the setup draft, then start it (roadmap R2-P6 task 6). */
export function useCreateAndStartRun() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: async (body: CreateRunRequest) => {
      const created = (await apiPost<SimulationState>('/simulation/runs', body)).data
      const start: StartRequest = { mode: body.mode, speed_factor: body.speed_factor }
      return (
        await apiPost<SimulationState>(`/simulation/runs/${encodeURIComponent(created.run_id)}/start`, start)
      ).data
    },
    onSuccess: (state) => {
      client.setQueryData(['run', state.run_id], state)
      void client.invalidateQueries({ queryKey: ['runs'] })
    },
  })
}
