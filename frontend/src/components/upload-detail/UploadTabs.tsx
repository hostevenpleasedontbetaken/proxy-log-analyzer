import { useSearchParams } from 'react-router'
import { EntriesTab } from '@/components/upload-detail/entries/EntriesTab'
import { IncidentsTab } from '@/components/upload-detail/incidents/IncidentsTab'
import { OverviewTab } from '@/components/upload-detail/overview/OverviewTab'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import type { UploadDetail } from '@/lib/types'

const TABS = ['overview', 'incidents', 'entries'] as const
type Tab = (typeof TABS)[number]

/**
 * Overview → Incidents → Entries: summary, then what to look at, then the evidence. The tab is in the URL (?tab=incidents)
 * so links, reloads and the back button keep it; Overview is the default and has no parameter.
 */
export function UploadTabs({ upload }: { upload: UploadDetail }) {
  const [searchParams, setSearchParams] = useSearchParams()
  const tab: Tab = TABS.find((t) => t === searchParams.get('tab')) ?? 'overview'
  const incidentCount = upload.stats?.detection.incidents

  function selectTab(next: string) {
    // A new tab starts unfiltered: other tabs' parameters (e.g. ?band=) are dropped.
    setSearchParams(next === 'overview' ? {} : { tab: next })
  }

  return (
    <Tabs value={tab} onValueChange={selectTab} className="gap-4">
      <TabsList>
        <TabsTrigger value="overview">Overview</TabsTrigger>
        <TabsTrigger value="incidents">
          Incidents{incidentCount !== undefined && <span className="tabular-nums">({incidentCount})</span>}
        </TabsTrigger>
        <TabsTrigger value="entries">Entries</TabsTrigger>
      </TabsList>
      <TabsContent value="overview">
        <OverviewTab upload={upload} />
      </TabsContent>
      <TabsContent value="incidents">
        <IncidentsTab uploadId={upload.id} />
      </TabsContent>
      <TabsContent value="entries">
        <EntriesTab uploadId={upload.id} />
      </TabsContent>
    </Tabs>
  )
}
