"use client"

import { cn } from "@/lib/utils"

const techIcons: Record<string, string> = {
  WordPress: "WP",
  Shopify: "SH",
  "Google Analytics": "GA",
  "No CRM": "!CRM",
  "No Analytics": "!GA",
  React: "RE",
  Vue: "VU",
  Wix: "WX",
}

interface TechStackPillsProps {
  stack: Record<string, string>
  max?: number
  className?: string
}

export function TechStackPills({ stack, max = 3, className }: TechStackPillsProps) {
  const entries = Object.entries(stack)
  const visible = entries.slice(0, max)
  const overflow = entries.length - max

  return (
    <div className={cn("flex flex-wrap gap-1", className)}>
      {visible.map(([key, value]) => (
        <span
          key={key}
          className="inline-flex items-center rounded-md bg-muted px-1.5 py-0.5 text-[10px] font-mono font-medium text-muted-foreground"
          title={`${key}: ${value}`}
        >
          {techIcons[value] ?? techIcons[key] ?? value.slice(0, 3).toUpperCase()}
        </span>
      ))}
      {overflow > 0 && (
        <span className="inline-flex items-center rounded-md bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
          +{overflow}
        </span>
      )}
    </div>
  )
}
