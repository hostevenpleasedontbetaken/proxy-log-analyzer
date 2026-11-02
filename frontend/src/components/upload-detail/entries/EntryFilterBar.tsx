import { SearchInput } from '@/components/upload-detail/entries/SearchInput'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import type { EntryFilters } from '@/lib/entry-filters'

type Props = { filters: EntryFilters; onChange: (changes: Partial<EntryFilters>) => void }

// Radix Select can't use "" as a value, so "no filter" is "any".
const ANY = 'any'

/** Search, user, action, flagged-only and minimum confidence, in one row above the table. */
export function EntryFilterBar({ filters, onChange }: Props) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-[2fr_1.5fr_auto_auto_auto] lg:items-center">
      <SearchInput
        label="Search host or URL"
        placeholder="Search host or URL"
        value={filters.q ?? ''}
        onChange={(q) => onChange({ q })}
      />
      <SearchInput
        label="User (exact login)"
        placeholder="User (exact login)"
        value={filters.user ?? ''}
        onChange={(user) => onChange({ user })}
      />
      <Select
        value={filters.action ?? ANY}
        onValueChange={(value) => onChange({ action: value === ANY ? undefined : (value as EntryFilters['action']) })}
      >
        <SelectTrigger aria-label="Action" className="w-full lg:w-36">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ANY}>Any action</SelectItem>
          <SelectItem value="Allowed">Allowed</SelectItem>
          <SelectItem value="Blocked">Blocked</SelectItem>
        </SelectContent>
      </Select>
      <Select
        value={filters.band ?? ANY}
        onValueChange={(value) => onChange({ band: value === ANY ? undefined : (value as EntryFilters['band']) })}
      >
        <SelectTrigger aria-label="Minimum confidence" className="w-full lg:w-44">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ANY}>Any confidence</SelectItem>
          <SelectItem value="Medium">Medium or higher</SelectItem>
          <SelectItem value="High">High only</SelectItem>
        </SelectContent>
      </Select>
      <Label className="flex items-center gap-2 font-normal whitespace-nowrap">
        <Checkbox checked={filters.flagged ?? false} onCheckedChange={(checked) => onChange({ flagged: checked === true })} />
        Flagged only
      </Label>
    </div>
  )
}
