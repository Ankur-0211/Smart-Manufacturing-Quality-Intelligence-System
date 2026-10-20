/** Stateless prediction (POST /predict) and explanations (GET /predict/{id}/explain). */
import { useMutation, useQuery } from '@tanstack/react-query'

import { apiGet, apiPost, type Schemas } from './client'

export type PredictRequest = Schemas['PredictRequest']
export type PredictResponse = Schemas['PredictResponse']
export type LocalExplanation = Schemas['LocalExplanation']
export type ActiveModels = Schemas['ActiveModelsOut']

/** The server validates the recipe against the registry and persists the prediction. */
export function usePredict() {
  return useMutation({
    mutationFn: async (body: PredictRequest) => (await apiPost<PredictResponse>('/predict', body)).data,
  })
}

export function useExplanation(predictionId: string | null) {
  return useQuery({
    queryKey: ['explanation', predictionId],
    queryFn: async () =>
      (await apiGet<LocalExplanation>(`/predict/${encodeURIComponent(predictionId!)}/explain`)).data,
    enabled: Boolean(predictionId),
    staleTime: Infinity, // a stored explanation never changes
  })
}

export function useActiveModels() {
  return useQuery({
    queryKey: ['models', 'active'],
    queryFn: async () => (await apiGet<ActiveModels>('/models/active')).data,
    staleTime: 60_000,
  })
}
