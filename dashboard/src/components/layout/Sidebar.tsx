"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { cn } from "@/lib/utils"
import {
    LayoutDashboard,
    Building2,
    Zap,
    Mail,
    Bug,
    Settings,
    MapPin,
    MessageSquare,
    Wrench,
} from "lucide-react"

export function Sidebar() {
    const pathname = usePathname()

    const links = [
        { href: "/overview", label: "Overview", icon: LayoutDashboard },
        { href: "/companies", label: "Companies", icon: Building2 },
        { href: "/leads", label: "Leads", icon: Zap, badge: "847" },
        { href: "/campaigns", label: "Campaigns", icon: Mail },
        { href: "/conversations", label: "Conversations", icon: MessageSquare },
        { href: "/scrapers", label: "Scrapers", icon: Bug },
        { href: "/targeting", label: "Targeting", icon: MapPin },
        { href: "/settings", label: "Settings", icon: Settings },
        { href: "/tools", label: "Tools", icon: Wrench },
    ]

    return (
        <aside className="fixed inset-y-0 left-0 z-50 flex w-64 flex-col border-r border-border bg-card">
            <div className="flex h-16 items-center border-b border-border px-6">
                <Link href="/overview" className="flex items-center gap-2">
                    <span className="text-xl font-bold tracking-tighter text-accent">ABOX</span>
                    <span className="text-xs uppercase tracking-widest text-muted-foreground">Mission Control</span>
                </Link>
            </div>
            <nav className="flex-1 overflow-y-auto p-4">
                <ul className="space-y-1">
                    {links.map((link) => {
                        const isActive = pathname === link.href
                        const Icon = link.icon
                        return (
                            <li key={link.href}>
                                <Link
                                    href={link.href}
                                    className={cn(
                                        "group flex items-center justify-between rounded-md px-3 py-2 text-sm font-medium transition-colors",
                                        isActive
                                            ? "bg-accent/10 text-accent"
                                            : "text-muted-foreground hover:bg-muted hover:text-foreground"
                                    )}
                                >
                                    <div className="flex items-center gap-3">
                                        <Icon className="h-4 w-4" />
                                        {link.label}
                                    </div>
                                    {link.badge && (
                                        <span
                                            className={cn(
                                                "rounded-full px-2 py-0.5 text-xs font-semibold",
                                                isActive
                                                    ? "bg-accent/20 text-accent"
                                                    : "bg-muted text-foreground group-hover:bg-background"
                                            )}
                                        >
                                            {link.badge}
                                        </span>
                                    )}
                                </Link>
                            </li>
                        )
                    })}
                </ul>
            </nav>
            <div className="flex items-center justify-between border-t border-border p-4">
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <span className="relative flex h-2 w-2">
                        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-system-green opacity-75"></span>
                        <span className="relative inline-flex h-2 w-2 rounded-full bg-system-green"></span>
                    </span>
                    Pipeline Live
                </div>
                <div className="text-xs font-mono text-muted-foreground">v2.1.0</div>
            </div>
        </aside>
    )
}
