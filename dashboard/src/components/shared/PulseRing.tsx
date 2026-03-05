import { cn } from "@/lib/utils"

interface PulseRingProps {
  color?: string
  size?: "sm" | "md" | "lg"
  className?: string
}

export function PulseRing({ color = "bg-cyan", size = "md", className }: PulseRingProps) {
  const sizeMap = { sm: "h-2 w-2", md: "h-3 w-3", lg: "h-4 w-4" }
  const ringMap = { sm: "h-3 w-3", md: "h-5 w-5", lg: "h-7 w-7" }

  return (
    <span className={cn("relative inline-flex items-center justify-center", ringMap[size], className)}>
      <span className={cn("absolute inline-flex h-full w-full animate-ping rounded-full opacity-40", color)} />
      <span className={cn("relative inline-flex rounded-full", sizeMap[size], color)} />
    </span>
  )
}
