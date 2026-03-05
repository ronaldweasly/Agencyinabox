import { Sidebar } from "./Sidebar"
import { TopBar } from "./TopBar"

export function Shell({ children }: { children: React.ReactNode }) {
    return (
        <div className="flex min-h-screen bg-background text-foreground">
            <Sidebar />
            <div className="flex flex-1 flex-col pl-64">
                <TopBar />
                <main className="flex-1 overflow-auto">{children}</main>
            </div>
        </div>
    )
}
