import { Search } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Input } from '@/components/ui/input'

const DEBOUNCE_MS = 400

type Props = { value: string; onChange: (value: string) => void; label: string; placeholder: string }

/**
 * A text filter that applies itself once typing pauses (or on Enter), so each keystroke doesn't
 * fire a request. Follows `value` when it changes from outside (back button, "Clear filters").
 */
export function SearchInput({ value, onChange, label, placeholder }: Props) {
  const [draft, setDraft] = useState(value)
  const [applied, setApplied] = useState(value)

  // The URL changed without typing here: show the new value.
  if (value !== applied) {
    setApplied(value)
    setDraft(value)
  }

  useEffect(() => {
    if (draft.trim() === value) return
    const timer = setTimeout(() => onChange(draft.trim()), DEBOUNCE_MS)
    return () => clearTimeout(timer)
  }, [draft, value, onChange])

  return (
    <div className="relative">
      <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
      <Input
        type="search"
        aria-label={label}
        placeholder={placeholder}
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        onKeyDown={(event) => event.key === 'Enter' && onChange(draft.trim())}
        className="pl-8"
      />
    </div>
  )
}
