"use client"

import { usePathname } from "next/navigation"
import { Bell, Search } from "lucide-react"
import { Input } from "@/components/ui/input"

export function TopBar() {
    const pathname = usePathname()
    const pageTitle = pathname.split("/")[1] || "Overview"
    const formattedTitle = pageTitle.charAt(0).toUpperCase() + pageTitle.slice(1)

    return (
        <header className="sticky top-0 z-40 flex h-16 w-full items-center justify-between border-b border-border bg-background/80 px-6 backdrop-blur-md">
            <div className="flex items-center gap-4">
                <h1 className="text-xl font-semibold tracking-tight">{formattedTitle}</h1>
                <div className="h-4 w-px bg-border"></div>
                <span className="text-sm text-muted-foreground">Agency-in-a-Box Intelligence Platform</span>
            </div>

            <div className="flex items-center gap-6">
                <div className="relative w-64">
                    <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                    <Input
                        type="search"
                        placeholder="Search companies, leads..."
                        className="h-9 w-full rounded-md border-border bg-muted pl-9 text-sm focus-visible:ring-accent"
                    />
                </div>

                <button className="relative text-muted-foreground hover:text-foreground transition-colors">
                    <Bell className="h-5 w-5" />
                    <span className="absolute -right-1 -top-1 flex h-3 w-3 items-center justify-center rounded-full bg-hot text-[8px] font-bold text-white shadow-sm ring-2 ring-background">
                        3
                    </span>
                </button>
            </div>
        </header>
    )
}
