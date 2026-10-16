/** Reference data a run is built from (GET /machines, /products, /materials; POST /materials). */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiGet, apiPost, type Schemas } from './client'

export type Machine = Schemas['MachineOut']
export type Product = Schemas['ProductOut']
export type MaterialLot = Schemas['MaterialLotOut']
export type MaterialLotCreate = Schemas['MaterialLotCreate']

const REFERENCE_STALE_MS = 60_000

export function useMachines() {
  return useQuery({
    queryKey: ['machines'],
    queryFn: async () => (await apiGet<Machine[]>('/machines')).data,
    staleTime: REFERENCE_STALE_MS,
  })
}

export function useProducts() {
  return useQuery({
    queryKey: ['products'],
    queryFn: async () => (await apiGet<Product[]>('/products')).data,
    staleTime: REFERENCE_STALE_MS,
  })
}

export function useMaterials() {
  return useQuery({
    queryKey: ['materials'],
    queryFn: async () => (await apiGet<MaterialLot[]>('/materials')).data,
    staleTime: REFERENCE_STALE_MS,
  })
}

/** Lot attributes are checked against the registry server-side (422 with per-field details). */
export function useCreateMaterial() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: async (body: MaterialLotCreate) => (await apiPost<MaterialLot>('/materials', body)).data,
    onSuccess: () => void client.invalidateQueries({ queryKey: ['materials'] }),
  })
}
