"use client"

import { Shell } from "@/components/layout/Shell"
import { StatsBar } from "@/components/overview/StatsBar"
import { PipelineFlow } from "@/components/overview/PipelineFlow"
import { QueueDepthCards } from "@/components/overview/QueueDepthCard"
import { LiveFeed } from "@/components/overview/LiveFeed"
import { OverviewCharts } from "@/components/overview/OverviewCharts"

export default function OverviewPage() {
  return (
    <Shell>
      <div className="flex flex-col gap-6 p-6 lg:flex-row">
        {/* Main content — left 2/3 */}
        <div className="flex min-w-0 flex-1 flex-col gap-6">
          <StatsBar />
          <PipelineFlow />
          <QueueDepthCards />
          <OverviewCharts />
        </div>

        {/* Live Feed — right 1/3 */}
        <div className="w-full lg:w-[380px]">
          <div className="sticky top-20">
            <LiveFeed />
          </div>
        </div>
      </div>
    </Shell>
  )
}
