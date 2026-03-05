"use client"

import { useState } from "react"
import { motion } from "framer-motion"
import useSWR from "swr"
import { Shell } from "@/components/layout/Shell"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Slider } from "@/components/ui/slider"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { fetcher, apiPost } from "@/lib/api"
import {
  CheckCircle2,
  XCircle,
  Loader2,
  Save,
  Zap,
  Mail,
  Key,
  Bell,
} from "lucide-react"
import { cn } from "@/lib/utils"

interface SettingsData {
  scoring: {
    hot_threshold: number
    warm_threshold: number
    auto_activate: number
    rescore_days: number
  }
  campaigns: {
    api_key: string
    daily_limit: number
    cooling_days: number
  }
  api_keys: Record<string, string>
  notifications: {
    telegram_token: string
    telegram_chat_id: string
    alerts: Record<string, boolean>
  }
}

function TestConnectionButton({ service }: { service: string }) {
  const [state, setState] = useState<"idle" | "loading" | "ok" | "error">("idle")

  async function test() {
    setState("loading")
    try {
      await apiPost("/api/settings/test-connection", { service })
      setState("ok")
      setTimeout(() => setState("idle"), 3000)
    } catch {
      setState("error")
      setTimeout(() => setState("idle"), 3000)
    }
  }

  return (
    <Button variant="outline" size="sm" className="gap-1.5 text-xs" onClick={test} disabled={state === "loading"}>
      {state === "loading" && <Loader2 className="h-3 w-3 animate-spin" />}
      {state === "ok" && <CheckCircle2 className="h-3 w-3 text-system-green" />}
      {state === "error" && <XCircle className="h-3 w-3 text-system-red" />}
      {state === "idle" && "Test"}
      {state === "loading" && "Testing..."}
      {state === "ok" && "Connected"}
      {state === "error" && "Failed"}
    </Button>
  )
}

export default function SettingsPage() {
  const { data } = useSWR<SettingsData>("/api/settings", fetcher)
  const s = data?.scoring
  const c = data?.campaigns
  const n = data?.notifications

  const [hotThreshold, setHotThreshold] = useState(s?.hot_threshold ?? 70)
  const [warmThreshold, setWarmThreshold] = useState(s?.warm_threshold ?? 50)
  const [autoActivate, setAutoActivate] = useState(s?.auto_activate ?? 65)

  return (
    <Shell>
      <div className="mx-auto max-w-4xl p-6">
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
          <Tabs defaultValue="scoring" className="space-y-6">
            <TabsList className="bg-muted">
              <TabsTrigger value="scoring" className="gap-1.5"><Zap className="h-3.5 w-3.5" /> Scoring</TabsTrigger>
              <TabsTrigger value="campaigns" className="gap-1.5"><Mail className="h-3.5 w-3.5" /> Campaigns</TabsTrigger>
              <TabsTrigger value="api_keys" className="gap-1.5"><Key className="h-3.5 w-3.5" /> API Keys</TabsTrigger>
              <TabsTrigger value="notifications" className="gap-1.5"><Bell className="h-3.5 w-3.5" /> Notifications</TabsTrigger>
            </TabsList>

            {/* Scoring */}
            <TabsContent value="scoring">
              <Card>
                <CardHeader><CardTitle>Scoring Thresholds</CardTitle></CardHeader>
                <CardContent className="space-y-6">
                  <div>
                    <Label className="mb-2 block">Hot Threshold: <span className="font-mono text-accent">{hotThreshold}</span></Label>
                    <Slider min={0} max={100} step={5} value={[hotThreshold]} onValueChange={([v]) => setHotThreshold(v)} />
                  </div>
                  <div>
                    <Label className="mb-2 block">Warm Threshold: <span className="font-mono text-accent">{warmThreshold}</span></Label>
                    <Slider min={0} max={100} step={5} value={[warmThreshold]} onValueChange={([v]) => setWarmThreshold(v)} />
                  </div>
                  <div>
                    <Label className="mb-2 block">Auto-Activate Score: <span className="font-mono text-accent">{autoActivate}</span></Label>
                    <Slider min={0} max={100} step={5} value={[autoActivate]} onValueChange={([v]) => setAutoActivate(v)} />
                  </div>
                  <div>
                    <Label className="mb-2 block">Re-score Interval</Label>
                    <select className="rounded-md border border-border bg-muted px-3 py-2 text-sm">
                      <option value="7">7 days</option>
                      <option value="14">14 days</option>
                      <option value="30">30 days</option>
                    </select>
                  </div>
                  <Button className="gap-1.5 bg-accent text-background hover:bg-accent/80">
                    <Save className="h-4 w-4" /> Save Changes
                  </Button>
                </CardContent>
              </Card>
            </TabsContent>

            {/* Campaigns */}
            <TabsContent value="campaigns">
              <Card>
                <CardHeader><CardTitle>Campaign Configuration</CardTitle></CardHeader>
                <CardContent className="space-y-4">
                  <div>
                    <Label className="mb-2 block">Instantly.ai API Key</Label>
                    <Input type="password" defaultValue={c?.api_key ?? ""} className="bg-muted border-border font-mono" />
                  </div>
                  <div>
                    <Label className="mb-2 block">Daily Send Limit</Label>
                    <Input type="number" defaultValue={c?.daily_limit ?? 200} className="bg-muted border-border font-mono w-32" />
                  </div>
                  <div>
                    <Label className="mb-2 block">Cooling Period After Bounce</Label>
                    <select className="rounded-md border border-border bg-muted px-3 py-2 text-sm">
                      <option value="30">30 days</option>
                      <option value="60">60 days</option>
                      <option value="90">90 days</option>
                    </select>
                  </div>
                  <Button className="gap-1.5 bg-accent text-background hover:bg-accent/80">
                    <Save className="h-4 w-4" /> Save Changes
                  </Button>
                </CardContent>
              </Card>
            </TabsContent>

            {/* API Keys */}
            <TabsContent value="api_keys">
              <Card>
                <CardHeader><CardTitle>API Keys</CardTitle></CardHeader>
                <CardContent className="space-y-4">
                  {["Hunter.io", "NeverBounce", "ZeroBounce", "Clearbit", "PageSpeed API"].map((name) => {
                    const key = name.toLowerCase().replace(/[.\s]/g, "")
                    return (
                      <div key={name} className="flex items-end gap-3">
                        <div className="flex-1">
                          <Label className="mb-2 block">{name}</Label>
                          <Input
                            type="password"
                            defaultValue={data?.api_keys?.[key] ?? ""}
                            className="bg-muted border-border font-mono"
                            placeholder="Enter API key..."
                          />
                        </div>
                        <TestConnectionButton service={key} />
                      </div>
                    )
                  })}
                  <Button className="mt-4 gap-1.5 bg-accent text-background hover:bg-accent/80">
                    <Save className="h-4 w-4" /> Save All Keys
                  </Button>
                </CardContent>
              </Card>
            </TabsContent>

            {/* Notifications */}
            <TabsContent value="notifications">
              <Card>
                <CardHeader><CardTitle>Notifications</CardTitle></CardHeader>
                <CardContent className="space-y-6">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label className="mb-2 block">Telegram Bot Token</Label>
                      <Input type="password" defaultValue={n?.telegram_token ?? ""} className="bg-muted border-border font-mono" />
                    </div>
                    <div>
                      <Label className="mb-2 block">Telegram Chat ID</Label>
                      <Input type="text" defaultValue={n?.telegram_chat_id ?? ""} className="bg-muted border-border font-mono" />
                    </div>
                  </div>
                  <div>
                    <Label className="mb-3 block">Alert Triggers</Label>
                    <div className="space-y-2">
                      {[
                        { key: "hot_lead", label: "New hot lead" },
                        { key: "reply", label: "Reply received" },
                        { key: "queue_stalled", label: "Queue stalled" },
                        { key: "worker_crashed", label: "Worker crashed" },
                        { key: "daily_summary", label: "Daily summary" },
                      ].map((alert) => (
                        <label key={alert.key} className="flex items-center gap-3 rounded-lg border border-border bg-[var(--bg2)] p-3 cursor-pointer hover:bg-muted transition-colors">
                          <input
                            type="checkbox"
                            defaultChecked={n?.alerts?.[alert.key] ?? true}
                            className="rounded border-border"
                          />
                          <span className="text-sm">{alert.label}</span>
                        </label>
                      ))}
                    </div>
                  </div>
                  <Button className="gap-1.5 bg-accent text-background hover:bg-accent/80">
                    <Save className="h-4 w-4" /> Save Notifications
                  </Button>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </motion.div>
      </div>
    </Shell>
  )
}
