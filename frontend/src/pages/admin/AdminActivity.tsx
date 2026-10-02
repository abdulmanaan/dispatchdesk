import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { Card, ErrorNote, PageHeader } from '../../components/Card'
import { Pagination, Tabs } from '../../components/Controls'
import { Spinner } from '../../components/Spinner'
import { api } from '../../lib/api'
import { describeEvent, isWarningEvent } from '../../lib/events'
import { formatWhen, orderRef } from '../../lib/format'
import type { AuditEntry, Page } from '../../lib/types'

const PAGE_SIZE = 20
type Filter = 'all' | 'order.' | 'driver.'

export function AdminActivity() {
  const [filter, setFilter] = useState<Filter>('all')
  const [page, setPage] = useState(1)
  const log = useQuery({
    queryKey: ['audit', filter, page],
    queryFn: () =>
      api<Page<AuditEntry>>('/audit-logs', {
        query: { action: filter === 'all' ? undefined : filter, page, page_size: PAGE_SIZE },
      }),
    refetchInterval: 15_000,
    placeholderData: (previous) => previous,
  })

  return (
    <>
      <PageHeader title="Activity" subtitle="Every change, who made it and when." />
      <Tabs
        label="Filter activity"
        value={filter}
        onChange={(v) => {
          setFilter(v)
          setPage(1)
        }}
        options={[
          { value: 'all', label: 'Everything' },
          { value: 'order.', label: 'Orders' },
          { value: 'driver.', label: 'Drivers' },
        ]}
      />
      {log.isPending && <Spinner className="size-6 text-muted" />}
      {log.isError && <ErrorNote message={log.error.message} />}
      {log.data && (
        <div className="grid gap-4">
          <Card className="overflow-hidden">
            <ul className="divide-y divide-line">
              {log.data.items.map((entry) => (
                <li
                  key={entry.id}
                  className="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-4 px-6 py-4"
                >
                  <div className="grid min-w-0 gap-0.5">
                    <span className={isWarningEvent(entry) ? 'text-danger' : ''}>{describeEvent(entry)}</span>
                    <span className="truncate text-[13px] text-muted">
                      {entry.entity_type === 'order' && entry.entity_id
                        ? `Order ${orderRef(entry.entity_id)}`
                        : 'Driver'}
                      {' · '}
                      {entry.actor_name ?? 'System'}
                    </span>
                  </div>
                  <span className="text-[13px] text-muted tabular-nums">{formatWhen(entry.created_at)}</span>
                </li>
              ))}
            </ul>
          </Card>
          <Pagination
            page={page}
            pages={log.data.pages}
            total={log.data.total}
            pageSize={PAGE_SIZE}
            onPage={setPage}
          />
        </div>
      )}
    </>
  )
}
