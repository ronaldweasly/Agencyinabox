"use client"

import { motion } from "framer-motion"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { CalendarCheck, ThumbsDown, ExternalLink } from "lucide-react"
import type { Campaign } from "@/lib/types"
import { cn } from "@/lib/utils"

interface ReplyIntelligenceProps {
  replies: Campaign[]
}

const sentimentColor = {
  positive: "bg-system-green/20 text-system-green border-system-green/30",
  negative: "bg-system-red/20 text-system-red border-system-red/30",
  neutral: "bg-muted text-muted-foreground",
}

export function ReplyIntelligence({ replies }: ReplyIntelligenceProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.5, duration: 0.4 }}
      className="rounded-lg border border-border bg-card p-4"
    >
      <h3 className="mb-4 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
        Reply Intelligence
      </h3>
      <div className="space-y-3">
        {replies.length > 0 ? replies.map((r) => (
          <div key={r.id} className="rounded-lg border border-border bg-[var(--bg2)] p-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">{r.campaign_name}</span>
              {r.reply_sentiment && (
                <Badge variant="outline" className={cn("text-[10px]", sentimentColor[r.reply_sentiment])}>
                  {r.reply_sentiment}
                </Badge>
              )}
            </div>
            {r.reply_text_snippet && (
              <p className="mt-2 text-xs italic text-muted-foreground leading-relaxed">
                &ldquo;{r.reply_text_snippet}&rdquo;
              </p>
            )}
            <div className="mt-3 flex items-center gap-2">
              <Button variant="outline" size="sm" className="gap-1.5 text-xs">
                <CalendarCheck className="h-3 w-3" /> Mark as Booked
              </Button>
              <Button variant="outline" size="sm" className="gap-1.5 text-xs">
                <ThumbsDown className="h-3 w-3" /> Not Interested
              </Button>
              <Button variant="ghost" size="sm" className="gap-1.5 text-xs">
                <ExternalLink className="h-3 w-3" /> Forward to CRM
              </Button>
            </div>
          </div>
        )) : (
          <p className="text-sm text-muted-foreground">No replies needing review.</p>
        )}
      </div>
    </motion.div>
  )
}
