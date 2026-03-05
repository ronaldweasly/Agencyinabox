"use client"

import { useState } from 'react'
import { Shell } from '@/components/layout/Shell'
import { motion, AnimatePresence } from 'framer-motion'
import useSWR from 'swr'
import {
  Key, CheckCircle2, XCircle, AlertTriangle,
  Eye, EyeOff, RefreshCw, ExternalLink, Plus,
  ToggleLeft, ToggleRight, Activity, Cpu
} from 'lucide-react'
import type { ApiKey, ToolStatus, CompetitorSignal } from '@/lib/types'
import { mockCompetitorSignals } from '@/lib/mockData'

const fetcher = (url: string) => fetch(url).then(r => r.json())

const CATEGORY_COLORS: Record<string, string> = {
  ai:             'var(--accent2)',
  scraping:       'var(--accent)',
  enrichment:     'var(--green)',
  email:          'var(--yellow)',
  outreach:       'var(--orange)',
  infrastructure: 'var(--cold)',
}

const CATEGORY_LABELS: Record<string, string> = {
  ai: 'AI', scraping: 'Scraping', enrichment: 'Enrichment',
  email: 'Email', outreach: 'Outreach', infrastructure: 'Infrastructure',
}

function ConnectionStatus({ connected, latency }: { connected: boolean; latency: number | null }) {
  if (connected) {
    return (
      <div className="flex items-center gap-1.5 text-xs font-medium"
           style={{ color: 'var(--green)' }}>
        <CheckCircle2 className="h-3.5 w-3.5" />
        Connected {latency && <span className="text-muted-foreground font-mono">{latency}ms</span>}
      </div>
    )
  }
  return (
    <div className="flex items-center gap-1.5 text-xs font-medium"
         style={{ color: 'var(--red)' }}>
      <XCircle className="h-3.5 w-3.5" />
      Disconnected
    </div>
  )
}

function UsageBar({ used, limit }: { used: number; limit: number | null }) {
  if (!limit) return <span className="text-xs text-muted-foreground">Unlimited</span>
  const pct = Math.min(100, (used / limit) * 100)
  const color = pct > 90 ? 'var(--red)' : pct > 70 ? 'var(--yellow)' : 'var(--green)'
  return (
    <div className="flex items-center gap-2 w-full">
      <div className="flex-1 h-1 rounded-full bg-white/10 overflow-hidden">
        <div className="h-full rounded-full transition-all"
             style={{ width: `${pct}%`, backgroundColor: color }} />
      </div>
      <span className="text-xs font-mono text-muted-foreground whitespace-nowrap">
        {(used / 1000).toFixed(0)}K / {(limit / 1000).toFixed(0)}K
      </span>
    </div>
  )
}

export default function ToolsPage() {
  const { data, mutate } = useSWR('/api/tools', fetcher, { refreshInterval: 30000 })
  const apiKeys: ApiKey[] = data?.api_keys ?? []
  const tools: ToolStatus[] = data?.tools ?? []

  const [activeTab, setActiveTab] = useState<'keys' | 'tools'>('keys')
  const [visibleKeys, setVisibleKeys] = useState<Set<string>>(new Set())
  const [testingIds, setTestingIds] = useState<Set<string>>(new Set())
  const [testResults, setTestResults] = useState<Record<string, { ok: boolean; ms: number }>>({})
  const [showAddKey, setShowAddKey] = useState(false)
  const [newService, setNewService] = useState('')
  const [newLabel, setNewLabel] = useState('')
  const [newKey, setNewKey] = useState('')
  const [newCategory, setNewCategory] = useState<ApiKey['category']>('enrichment')

  const filterCategory = (items: ApiKey[]) =>
    [...items].sort((a, b) => {
      const order = ['infrastructure', 'ai', 'scraping', 'enrichment', 'email', 'outreach']
      return order.indexOf(a.category) - order.indexOf(b.category)
    })

  const connectedCount = apiKeys.filter(k => k.is_connected && k.is_active).length
  const healthyTools = tools.filter(t => t.is_healthy && t.is_enabled).length

  async function handleTest(key: ApiKey) {
    setTestingIds(prev => new Set([...prev, key.id]))
    try {
      const res = await fetch('/api/tools', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'test', service: key.service }),
      })
      const result = await res.json()
      setTestResults(prev => ({
        ...prev,
        [key.id]: { ok: result.connected, ms: result.latency_ms }
      }))
    } catch {
      setTestResults(prev => ({ ...prev, [key.id]: { ok: false, ms: 0 } }))
    } finally {
      setTestingIds(prev => { const s = new Set(prev); s.delete(key.id); return s })
    }
    mutate()
  }

  async function handleToggleTool(id: string, current: boolean) {
    await fetch('/api/tools', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'toggle_tool', id, is_enabled: !current }),
    })
    mutate()
  }

  async function handleSaveKey() {
    if (!newService.trim() || !newKey.trim()) return
    await fetch('/api/tools', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        action: 'add_key',
        service: newService.trim(),
        label: newLabel.trim() || newService.trim(),
        key: newKey.trim(),
        category: newCategory,
      }),
    })
    setShowAddKey(false)
    setNewService(''); setNewLabel(''); setNewKey('')
    mutate()
  }

  return (
    <Shell>
      <div className="flex flex-col gap-6 p-6">

        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight"
                style={{ fontFamily: 'var(--font-syne)' }}>
              API Keys &amp; Tools
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Manage integrations, test connections, control tools
            </p>
          </div>
          {activeTab === 'keys' && (
            <button
              onClick={() => setShowAddKey(true)}
              className="flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold
                         transition-all hover:opacity-80 active:scale-95"
              style={{ backgroundColor: 'var(--accent)', color: 'var(--bg)' }}
            >
              <Plus className="h-4 w-4" />
              Add Key
            </button>
          )}
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[
            { label: 'Connected APIs', value: `${connectedCount}/${apiKeys.length}`,
              icon: Key, color: 'var(--accent)' },
            { label: 'Healthy Tools', value: `${healthyTools}/${tools.length}`,
              icon: Activity, color: 'var(--green)' },
            { label: 'Errors Today', value: tools.reduce((s, t) => s + t.error_count_today, 0),
              icon: AlertTriangle, color: 'var(--red)' },
            { label: 'Total Runs Today', value: tools.reduce((s, t) => s + t.runs_today, 0),
              icon: Cpu, color: 'var(--yellow)' },
          ].map((stat, i) => {
            const Icon = stat.icon
            return (
              <motion.div key={stat.label}
                initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.07 }}
                className="rounded-lg border border-border bg-card p-4"
              >
                <div className="flex items-center gap-2 text-xs text-muted-foreground mb-2">
                  <Icon className="h-3.5 w-3.5" style={{ color: stat.color }} />
                  {stat.label}
                </div>
                <div className="font-mono text-2xl font-bold"
                     style={{ color: stat.color }}>{stat.value}</div>
              </motion.div>
            )
          })}
        </div>

        {/* Tabs */}
        <div className="flex gap-1 rounded-lg border border-border bg-card p-1 w-fit">
          {(['keys', 'tools'] as const).map(tab => (
            <button key={tab} onClick={() => setActiveTab(tab)}
              className={`rounded-md px-4 py-1.5 text-sm font-medium capitalize transition-all ${
                activeTab === tab
                  ? 'text-[var(--bg)] shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
              style={activeTab === tab ? { backgroundColor: 'var(--accent)' } : {}}
            >
              {tab === 'keys' ? 'API Keys' : 'Tools'}
            </button>
          ))}
        </div>

        {/* API Keys tab */}
        {activeTab === 'keys' && (
          <div className="flex flex-col gap-3">
            {filterCategory(apiKeys).map((key, i) => {
              const isVisible = visibleKeys.has(key.id)
              const isTesting = testingIds.has(key.id)
              const testResult = testResults[key.id]
              const categoryColor = CATEGORY_COLORS[key.category]

              return (
                <motion.div key={key.id}
                  initial={{ opacity: 0, x: -12 }} animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.05 }}
                  className="rounded-lg border border-border bg-card p-4"
                >
                  <div className="flex items-start gap-4">
                    {/* Category LED */}
                    <div className="mt-0.5 h-2 w-2 rounded-full shrink-0"
                         style={{
                           backgroundColor: key.is_connected ? categoryColor : 'var(--cold)',
                           boxShadow: key.is_connected ? `0 0 8px ${categoryColor}` : 'none',
                         }} />

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-4 flex-wrap">
                        <div className="flex items-center gap-3">
                          <span className="font-semibold text-sm">{key.label}</span>
                          <span className="text-[10px] font-medium uppercase tracking-wider
                                         px-1.5 py-0.5 rounded"
                                style={{
                                  backgroundColor: `${categoryColor}20`,
                                  color: categoryColor,
                                }}>
                            {CATEGORY_LABELS[key.category]}
                          </span>
                          {key.required && (
                            <span className="text-[10px] font-medium text-[var(--red)]">
                              REQUIRED
                            </span>
                          )}
                        </div>
                        <ConnectionStatus
                          connected={testResult ? testResult.ok : key.is_connected}
                          latency={testResult?.ms ?? key.last_test_latency_ms}
                        />
                      </div>

                      {/* Key display */}
                      <div className="mt-2 flex items-center gap-2">
                        <code className="font-mono text-xs text-muted-foreground bg-black/30
                                        rounded px-2 py-1 flex-1 min-w-0 truncate">
                          {isVisible ? key.key_masked : '\u2022'.repeat(24)}
                        </code>
                        <button onClick={() => setVisibleKeys(prev => {
                          const s = new Set(prev)
                          s.has(key.id) ? s.delete(key.id) : s.add(key.id)
                          return s
                        })}
                          className="shrink-0 rounded p-1.5 text-muted-foreground
                                     hover:bg-white/5 transition-colors">
                          {isVisible ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                        </button>
                      </div>

                      {/* Usage */}
                      <div className="mt-2">
                        <UsageBar used={key.usage_this_month} limit={key.usage_limit} />
                      </div>

                      {/* Actions */}
                      <div className="mt-3 flex items-center gap-2 flex-wrap">
                        <button onClick={() => handleTest(key)}
                          disabled={isTesting}
                          className="flex items-center gap-1.5 rounded-md border border-border
                                     px-3 py-1.5 text-xs font-medium transition-all
                                     hover:border-white/20 disabled:opacity-50"
                        >
                          <RefreshCw className={`h-3 w-3 ${isTesting ? 'animate-spin' : ''}`} />
                          {isTesting ? 'Testing...' : 'Test Connection'}
                        </button>
                        <a href={key.docs_url} target="_blank" rel="noopener noreferrer"
                          className="flex items-center gap-1.5 rounded-md border border-border
                                     px-3 py-1.5 text-xs font-medium text-muted-foreground
                                     transition-all hover:border-white/20 hover:text-foreground">
                          <ExternalLink className="h-3 w-3" />
                          Docs
                        </a>
                      </div>
                    </div>
                  </div>
                </motion.div>
              )
            })}
          </div>
        )}

        {/* Tools tab */}
        {activeTab === 'tools' && (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {tools.map((tool, i) => (
              <motion.div key={tool.id}
                initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.06 }}
                className={`rounded-lg border p-4 transition-all ${
                  !tool.is_enabled ? 'opacity-50 border-border bg-card' :
                  tool.is_healthy
                    ? 'border-[var(--green)]/20 bg-[var(--green)]/5'
                    : 'border-[var(--red)]/30 bg-[var(--red)]/5'
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <div className="h-2 w-2 rounded-full"
                           style={{
                             backgroundColor: !tool.is_enabled
                               ? 'var(--cold)'
                               : tool.is_healthy ? 'var(--green)' : 'var(--red)',
                             boxShadow: tool.is_enabled
                               ? `0 0 6px ${tool.is_healthy ? 'var(--green)' : 'var(--red)'}`
                               : 'none',
                           }} />
                      <span className="font-semibold text-sm">{tool.name}</span>
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">{tool.description}</p>
                    <div className="mt-3 flex items-center gap-4 text-xs text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <Cpu className="h-3 w-3" />
                        {tool.runs_today} runs today
                      </span>
                      {tool.error_count_today > 0 && (
                        <span className="flex items-center gap-1"
                              style={{ color: 'var(--red)' }}>
                          <AlertTriangle className="h-3 w-3" />
                          {tool.error_count_today} errors
                        </span>
                      )}
                    </div>
                    {tool.depends_on.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {tool.depends_on.map(dep => (
                          <span key={dep}
                            className="rounded px-1.5 py-0.5 text-[10px] font-mono
                                       bg-white/5 text-muted-foreground">
                            {dep}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                  <button onClick={() => handleToggleTool(tool.id, tool.is_enabled)}
                    className="shrink-0 rounded p-1 transition-colors hover:bg-white/5">
                    {tool.is_enabled
                      ? <ToggleRight className="h-6 w-6" style={{ color: 'var(--green)' }} />
                      : <ToggleLeft className="h-6 w-6 text-muted-foreground" />
                    }
                  </button>
                </div>
              </motion.div>
            ))}
          </div>
        )}

        {/* Competitor Monitor */}
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3, duration: 0.4 }}>
          <div className="rounded-lg border border-border bg-card p-4">
            <h3 className="text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-4">
              🔍 Competitor Monitor — Latest Signals
            </h3>
            <div className="flex flex-col gap-3">
              {mockCompetitorSignals.map((sig) => (
                <div key={sig.id} className="flex items-start gap-3 rounded-md border border-border p-3 bg-[var(--bg2)]">
                  <div className={`mt-0.5 h-2 w-2 rounded-full shrink-0 ${
                    sig.has_weakness ? 'bg-system-green' : 'bg-muted-foreground'
                  }`} style={sig.has_weakness ? { boxShadow: '0 0 6px var(--green)' } : {}} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-sm">{sig.competitor_name}</span>
                      <span className="text-[10px] font-medium uppercase tracking-wider px-1.5 py-0.5 rounded bg-white/5 text-muted-foreground">
                        {sig.signal_type.replace(/_/g, ' ')}
                      </span>
                      {sig.has_weakness && (
                        <span className="text-[10px] font-medium" style={{ color: 'var(--green)' }}>
                          EXPLOITABLE
                        </span>
                      )}
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground leading-relaxed">{sig.detail}</p>
                    <a href={sig.competitor_url} target="_blank" rel="noopener noreferrer"
                       className="mt-1 inline-flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground transition-colors">
                      <ExternalLink className="h-3 w-3" /> {sig.competitor_url}
                    </a>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </motion.div>

        {/* Add Key Modal */}
        <AnimatePresence>
          {showAddKey && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              className="fixed inset-0 z-50 flex items-center justify-center p-4"
              style={{ backgroundColor: 'rgba(0,0,0,0.8)' }}
              onClick={e => { if (e.target === e.currentTarget) setShowAddKey(false) }}
            >
              <motion.div initial={{ scale: 0.95 }} animate={{ scale: 1 }} exit={{ scale: 0.95 }}
                className="w-full max-w-md rounded-xl border border-border p-6"
                style={{ backgroundColor: 'var(--bg2)' }}
              >
                <h2 className="text-lg font-bold mb-5">Add API Key</h2>
                <div className="flex flex-col gap-4">
                  <div>
                    <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2 block">
                      Service Name
                    </label>
                    <input type="text" value={newService}
                      onChange={e => setNewService(e.target.value)}
                      placeholder="e.g. clearbit"
                      className="w-full rounded-lg border border-border bg-[var(--bg3)]
                                 px-3 py-2 text-sm outline-none focus:border-[var(--accent)]
                                 placeholder:text-muted-foreground font-mono" />
                  </div>
                  <div>
                    <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2 block">
                      Display Label
                    </label>
                    <input type="text" value={newLabel}
                      onChange={e => setNewLabel(e.target.value)}
                      placeholder="e.g. Clearbit Enrichment"
                      className="w-full rounded-lg border border-border bg-[var(--bg3)]
                                 px-3 py-2 text-sm outline-none focus:border-[var(--accent)]
                                 placeholder:text-muted-foreground font-mono" />
                  </div>
                  <div>
                    <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2 block">
                      API Key
                    </label>
                    <input type="password" value={newKey}
                      onChange={e => setNewKey(e.target.value)}
                      placeholder="Paste your API key here"
                      className="w-full rounded-lg border border-border bg-[var(--bg3)]
                                 px-3 py-2 text-sm outline-none focus:border-[var(--accent)]
                                 placeholder:text-muted-foreground font-mono" />
                  </div>
                  <div>
                    <label className="text-xs font-semibold text-muted-foreground
                                     uppercase tracking-wider mb-2 block">Category</label>
                    <select value={newCategory}
                      onChange={e => setNewCategory(e.target.value as ApiKey['category'])}
                      className="w-full rounded-lg border border-border bg-[var(--bg3)]
                                 px-3 py-2 text-sm outline-none focus:border-[var(--accent)]"
                    >
                      {Object.entries(CATEGORY_LABELS).map(([val, label]) => (
                        <option key={val} value={val}>{label}</option>
                      ))}
                    </select>
                  </div>
                  <div className="flex gap-3 mt-2">
                    <button onClick={() => setShowAddKey(false)}
                      className="flex-1 rounded-lg border border-border py-2.5 text-sm
                                 font-medium hover:bg-white/5 transition-colors">
                      Cancel
                    </button>
                    <button onClick={handleSaveKey}
                      disabled={!newService.trim() || !newKey.trim()}
                      className="flex-1 rounded-lg py-2.5 text-sm font-semibold
                                 transition-all hover:opacity-80 disabled:opacity-40"
                      style={{ backgroundColor: 'var(--accent)', color: 'var(--bg)' }}>
                      Save Key
                    </button>
                  </div>
                </div>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>

      </div>
    </Shell>
  )
}
