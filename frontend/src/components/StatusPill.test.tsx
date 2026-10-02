import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { StatusPill } from './StatusPill'

describe('StatusPill', () => {
  it('shows delivered orders as a muted pill with a check icon', () => {
    const { container } = render(
      <StatusPill order={{ status: 'delivered', accepted_at: '2026-10-03T10:00:00Z' }} />,
    )

    const pill = screen.getByText('Delivered')
    expect(pill.className).toContain('bg-done-bg')
    expect(pill.className).not.toContain('accent')
    expect(container.querySelector('svg')).not.toBeNull()
  })

  it('has no icon for open orders', () => {
    const { container } = render(<StatusPill order={{ status: 'assigned', accepted_at: null }} />)

    expect(screen.getByText('Awaiting accept')).toBeInTheDocument()
    expect(container.querySelector('svg')).toBeNull()
  })
})
