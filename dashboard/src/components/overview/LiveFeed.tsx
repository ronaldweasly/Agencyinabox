"use client"

import { useState, useEffect, useRef } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { usePipelineFeed } from "@/hooks/usePipeline"
import { cn } from "@/lib/utils"
import { Pause, Play } from "lucide-react"

interface FeedEvent {
  id: string
  type: string
  source: string
  message: string
  timestamp: string
}

const badgeColor: Record<string, string> = {
  GOOGLE_MAPS: "bg-cyan/20 text-cyan",
  YELP: "bg-cyan/20 text-cyan",
  SSL_CERTS: "bg-cyan/20 text-cyan",
  AI_SCORE: "bg-purple/20 text-purple",
  EMAIL_SENT: "bg-system-green/20 text-system-green",
  REPLY: "bg-system-yellow/20 text-system-yellow",
  ERROR: "bg-system-red/20 text-system-red",
}

export function LiveFeed() {
  const { data } = usePipelineFeed() as { data: FeedEvent[] | undefined }
  const [paused, setPaused] = useState(false)
  const [events, setEvents] = useState<FeedEvent[]>([])
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (data && !paused) {
      setEvents(data.slice(0, 100))
    }
  }, [data, paused])

  useEffect(() => {
    if (!paused && scrollRef.current) {
      scrollRef.current.scrollTop = 0
    }
  }, [events, paused])

  return (
    <div className="flex h-full flex-col rounded-lg border border-border bg-card">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-system-green opacity-75" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-system-green" />
          </span>
          <h2 className="text-sm font-semibold uppercase tracking-widest text-muted-foreground">Live Feed</h2>
        </div>
        <button
          onClick={() => setPaused(!paused)}
          className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        >
          {paused ? <Play className="h-3.5 w-3.5" /> : <Pause className="h-3.5 w-3.5" />}
        </button>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto p-3" style={{ maxHeight: "520px" }}>
        <AnimatePresence initial={false}>
          {events.map((evt) => {
            const time = new Date(evt.timestamp).toLocaleTimeString("en-US", {
              hour12: false,
              hour: "2-digit",
              minute: "2-digit",
              second: "2-digit",
            })
            const isHot = evt.message.includes("HOT")
            return (
              <motion.div
                key={evt.id}
                initial={{ opacity: 0, y: -12, height: 0 }}
                animate={{ opacity: 1, y: 0, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ type: "spring", stiffness: 300, damping: 24 }}
                className={cn(
                  "mb-2 rounded-md border border-border bg-[var(--bg2)] px-3 py-2 text-xs",
                  isHot && "ring-1 ring-hot/30"
                )}
              >
                <div className="flex items-center gap-2">
                  <span className="font-mono text-[10px] text-muted-foreground">{time}</span>
                  <span
                    className={cn(
                      "rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase",
                      badgeColor[evt.source] ?? "bg-muted text-muted-foreground"
                    )}
                  >
                    {evt.source.replace(/_/g, " ")}
                  </span>
                </div>
                <p className={cn("mt-1 text-foreground/90", isHot && "font-semibold text-hot")}>
                  {evt.message}
                </p>
              </motion.div>
            )
          })}
        </AnimatePresence>
      </div>
    </div>
  )
}
