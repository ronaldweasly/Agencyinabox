import { cn } from "@/lib/utils"

interface StatusDotProps {
    status: "running" | "healthy" | "stalled" | "error" | "paused" | "backlogged"
    className?: string
}

export function StatusDot({ status, className }: StatusDotProps) {
    const colorMap = {
        running: "bg-system-green",
        healthy: "bg-system-green",
        stalled: "bg-system-orange",
        backlogged: "bg-system-yellow",
        error: "bg-system-red",
        paused: "bg-cold",
    }

    const isPulsing = status === "running" || status === "healthy"

    return (
        <div className={cn("relative flex h-3 w-3 items-center justify-center", className)}>
            {isPulsing && (
                <span
                    className={cn(
                        "absolute inline-flex h-full w-full animate-ping rounded-full opacity-75",
                        colorMap[status]
                    )}
                />
            )}
            <span className={cn("relative inline-flex h-2 w-2 rounded-full", colorMap[status])} />
        </div>
    )
}
