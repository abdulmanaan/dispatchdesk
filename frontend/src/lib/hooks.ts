import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from './api'
import type { AuditEntry, Order, OrderDetail, Page } from './types'

type OrderQuery = Record<string, string | number | boolean | string[] | undefined>

export function useOrders(query: OrderQuery, refetchInterval = 15_000) {
  return useQuery({
    queryKey: ['orders', query],
    queryFn: () => api<Page<Order>>('/orders', { query }),
    refetchInterval,
    placeholderData: (previous) => previous,
  })
}

export function useOrderDetail(id: string, enabled: boolean) {
  return useQuery({
    queryKey: ['order', id],
    queryFn: () => api<OrderDetail>(`/orders/${id}`),
    enabled,
  })
}

export function useOrderEvents(id: string, enabled: boolean) {
  return useQuery({
    queryKey: ['order', id, 'events'],
    queryFn: () => api<AuditEntry[]>(`/orders/${id}/events`),
    enabled,
  })
}

/**
 * A mutation that refreshes everything order-related afterwards, since one
 * action (e.g. a delivery) can change orders, drivers and stats at once.
 */
export function useOrderAction<TArgs, TResult = unknown>(run: (args: TArgs) => Promise<TResult>) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: run,
    onSettled: () => {
      for (const key of ['orders', 'order', 'driver', 'drivers', 'stats', 'audit', 'auth']) {
        queryClient.invalidateQueries({ queryKey: [key] })
      }
    },
  })
}
