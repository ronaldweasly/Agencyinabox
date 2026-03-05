import { cn } from "@/lib/utils"

interface ScoreBadgeProps {
    score: number
    tier: "hot" | "warm" | "cold" | "suppressed"
    className?: string
    size?: "sm" | "md" | "lg"
}

export function ScoreBadge({ score, tier, className, size = "md" }: ScoreBadgeProps) {
    const colorMap = {
        hot: "border-hot text-hot bg-hot/10 shadow-[0_0_10px_rgba(255,77,109,0.3)]",
        warm: "border-warm text-warm bg-warm/10",
        cold: "border-cold text-cold bg-cold/10",
        suppressed: "border-muted text-muted-foreground bg-muted",
    }

    const sizeMap = {
        sm: "h-6 text-xs px-2",
        md: "h-8 text-sm px-3",
        lg: "h-12 text-lg px-4 border-2 shadow-[0_0_15px_rgba(255,77,109,0.4)]",
    }

    return (
        <div
            className={cn(
                "inline-flex items-center justify-center rounded-full border font-mono font-medium tracking-tight",
                colorMap[tier],
                sizeMap[size],
                className
            )}
        >
            {tier === "hot" && <span className="mr-1.5 h-1.5 w-1.5 rounded-full bg-hot animate-pulse" />}
            {score.toString().padStart(2, "0")}
            {size !== "sm" && <span className="ml-1.5 uppercase font-sans text-[0.65em] opacity-80">{tier}</span>}
        </div>
    )
}
