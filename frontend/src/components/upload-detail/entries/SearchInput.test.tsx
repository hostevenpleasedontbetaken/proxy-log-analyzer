import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { SearchInput } from '@/components/upload-detail/entries/SearchInput'

describe('SearchInput', () => {
  it('applies the text once typing pauses, not on every keystroke', async () => {
    const onChange = vi.fn()
    render(<SearchInput label="Search" placeholder="" value="" onChange={onChange} />)

    await userEvent.type(screen.getByRole('searchbox', { name: 'Search' }), 'dropbin')
    expect(onChange).not.toHaveBeenCalled()
    await vi.waitFor(() => expect(onChange).toHaveBeenCalledWith('dropbin'), { timeout: 1000 })
    expect(onChange).toHaveBeenCalledTimes(1)
  })

  it('applies immediately on Enter', async () => {
    const onChange = vi.fn()
    render(<SearchInput label="Search" placeholder="" value="" onChange={onChange} />)
    await userEvent.type(screen.getByRole('searchbox', { name: 'Search' }), 'x{Enter}')
    expect(onChange).toHaveBeenCalledWith('x')
  })

  it('shows a new value set from outside, e.g. "Clear filters"', () => {
    const { rerender } = render(<SearchInput label="Search" placeholder="" value="old" onChange={() => {}} />)
    rerender(<SearchInput label="Search" placeholder="" value="" onChange={() => {}} />)
    expect(screen.getByRole('searchbox', { name: 'Search' })).toHaveValue('')
  })
})
