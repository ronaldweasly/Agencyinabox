"use client"

import { useState } from "react"
import { motion } from "framer-motion"
import { Button } from "@/components/ui/button"
import { Loader2, CheckCircle2, Rocket } from "lucide-react"
import { apiPost } from "@/lib/api"
import { cn } from "@/lib/utils"

interface LeadActivateButtonProps {
  leadId: string
  className?: string
  onActivated?: () => void
}

export function LeadActivateButton({ leadId, className, onActivated }: LeadActivateButtonProps) {
  const [state, setState] = useState<"idle" | "loading" | "done">("idle")

  async function handleActivate() {
    setState("loading")
    try {
      await apiPost(`/api/leads/${leadId}/activate`)
      setState("done")
      setTimeout(() => onActivated?.(), 1500)
    } catch {
      setState("idle")
    }
  }

  if (state === "done") {
    return (
      <motion.div
        initial={{ scale: 0.9 }}
        animate={{ scale: 1 }}
        className={cn("flex items-center gap-1.5 rounded-md bg-system-green/20 px-3 py-1.5 text-xs font-semibold text-system-green", className)}
      >
        <CheckCircle2 className="h-3.5 w-3.5" /> Activated!
      </motion.div>
    )
  }

  return (
    <Button
      variant="default"
      size="sm"
      disabled={state === "loading"}
      onClick={handleActivate}
      className={cn("gap-1.5 text-xs bg-accent text-background hover:bg-accent/80", className)}
    >
      {state === "loading" ? (
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
      ) : (
        <Rocket className="h-3.5 w-3.5" />
      )}
      {state === "loading" ? "Activating..." : "Activate"}
    </Button>
  )
}
