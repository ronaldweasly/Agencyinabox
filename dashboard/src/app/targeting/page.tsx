"use client"

import { useState } from 'react'
import { Shell } from '@/components/layout/Shell'
import { motion, AnimatePresence } from 'framer-motion'
import { MapPin, Plus, Trash2, ToggleLeft, ToggleRight,
         Target, Zap, Globe, Search, ChevronDown, AlertCircle } from 'lucide-react'
import useSWR from 'swr'
import type { ScrapeTarget, ScrapingCategory } from '@/lib/types'

const fetcher = (url: string) => fetch(url).then(r => r.json())

const US_STATES = [
  { code: 'AL', name: 'Alabama' }, { code: 'AK', name: 'Alaska' },
  { code: 'AZ', name: 'Arizona' }, { code: 'AR', name: 'Arkansas' },
  { code: 'CA', name: 'California' }, { code: 'CO', name: 'Colorado' },
  { code: 'CT', name: 'Connecticut' }, { code: 'DE', name: 'Delaware' },
  { code: 'FL', name: 'Florida' }, { code: 'GA', name: 'Georgia' },
  { code: 'HI', name: 'Hawaii' }, { code: 'ID', name: 'Idaho' },
  { code: 'IL', name: 'Illinois' }, { code: 'IN', name: 'Indiana' },
  { code: 'IA', name: 'Iowa' }, { code: 'KS', name: 'Kansas' },
  { code: 'KY', name: 'Kentucky' }, { code: 'LA', name: 'Louisiana' },
  { code: 'ME', name: 'Maine' }, { code: 'MD', name: 'Maryland' },
  { code: 'MA', name: 'Massachusetts' }, { code: 'MI', name: 'Michigan' },
  { code: 'MN', name: 'Minnesota' }, { code: 'MS', name: 'Mississippi' },
  { code: 'MO', name: 'Missouri' }, { code: 'MT', name: 'Montana' },
  { code: 'NE', name: 'Nebraska' }, { code: 'NV', name: 'Nevada' },
  { code: 'NH', name: 'New Hampshire' }, { code: 'NJ', name: 'New Jersey' },
  { code: 'NM', name: 'New Mexico' }, { code: 'NY', name: 'New York' },
  { code: 'NC', name: 'North Carolina' }, { code: 'ND', name: 'North Dakota' },
  { code: 'OH', name: 'Ohio' }, { code: 'OK', name: 'Oklahoma' },
  { code: 'OR', name: 'Oregon' }, { code: 'PA', name: 'Pennsylvania' },
  { code: 'RI', name: 'Rhode Island' }, { code: 'SC', name: 'South Carolina' },
  { code: 'SD', name: 'South Dakota' }, { code: 'TN', name: 'Tennessee' },
  { code: 'TX', name: 'Texas' }, { code: 'UT', name: 'Utah' },
  { code: 'VT', name: 'Vermont' }, { code: 'VA', name: 'Virginia' },
  { code: 'WA', name: 'Washington' }, { code: 'WV', name: 'West Virginia' },
  { code: 'WI', name: 'Wisconsin' }, { code: 'WY', name: 'Wyoming' },
]

type TargetType = 'state' | 'county' | 'city' | 'zipcode'
type Priority = 'high' | 'medium' | 'low'

function priorityColor(p: Priority) {
  if (p === 'high') return 'text-[var(--red)]'
  if (p === 'medium') return 'text-[var(--yellow)]'
  return 'text-[var(--cold)]'
}

function priorityBg(p: Priority) {
  if (p === 'high') return 'bg-[var(--red)]/10 border-[var(--red)]/30'
  if (p === 'medium') return 'bg-[var(--yellow)]/10 border-[var(--yellow)]/30'
  return 'bg-[var(--cold)]/10 border-[var(--cold)]/30'
}

function typeIcon(t: TargetType) {
  switch (t) {
    case 'state': return '\u{1F5FA}\u{FE0F}'
    case 'county': return '\u{1F4CD}'
    case 'city': return '\u{1F3D9}\u{FE0F}'
    case 'zipcode': return '\u{1F522}'
  }
}

function formatLeads(n: number) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`
  return n.toString()
}

export default function TargetingPage() {
  const { data, mutate } = useSWR('/api/targeting', fetcher, { refreshInterval: 30000 })

  const targets: ScrapeTarget[] = data?.targets ?? []
  const categories: ScrapingCategory[] = data?.categories ?? []
  const totalEstimated: number = data?.total_estimated_leads ?? 0

  const [activeTab, setActiveTab] = useState<'locations' | 'categories'>('locations')
  const [showAddModal, setShowAddModal] = useState(false)
  const [filterType, setFilterType] = useState<TargetType | 'all'>('all')
  const [searchQuery, setSearchQuery] = useState('')

  // Add target form state
  const [newType, setNewType] = useState<TargetType>('city')
  const [newState, setNewState] = useState('TX')
  const [newValue, setNewValue] = useState('')
  const [newLabel, setNewLabel] = useState('')
  const [newPriority, setNewPriority] = useState<Priority>('medium')

  const filteredTargets = targets.filter(t => {
    if (filterType !== 'all' && t.type !== filterType) return false
    if (searchQuery && !t.label.toLowerCase().includes(searchQuery.toLowerCase())) return false
    return true
  })

  const activeTargets = targets.filter(t => t.is_active)
  const totalCombos = activeTargets.length * categories.filter(c => c.is_active).length

  async function handleToggleTarget(id: string, current: boolean) {
    await fetch('/api/targeting', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'toggle', id, is_active: !current }),
    })
    mutate()
  }

  async function handleDeleteTarget(id: string) {
    await fetch('/api/targeting', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'delete', id }),
    })
    mutate()
  }

  async function handleAddTarget() {
    if (!newValue.trim()) return
    await fetch('/api/targeting', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        action: 'add',
        type: newType,
        value: newValue.trim(),
        label: newLabel.trim() || newValue.trim(),
        state: newState,
        priority: newPriority,
        is_active: true,
        estimated_leads: 0,
      }),
    })
    setShowAddModal(false)
    setNewValue('')
    setNewLabel('')
    mutate()
  }

  async function handleToggleCategory(id: string, current: boolean) {
    await fetch('/api/targeting', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'toggle_category', id, is_active: !current }),
    })
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
              Scrape Targeting
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Define exactly where your scrapers hunt for leads
            </p>
          </div>
          <button
            onClick={() => setShowAddModal(true)}
            className="flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold
                       transition-all hover:opacity-80 active:scale-95"
            style={{ backgroundColor: 'var(--accent)', color: 'var(--bg)' }}
          >
            <Plus className="h-4 w-4" />
            Add Target
          </button>
        </div>

        {/* KPI strip */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[
            { label: 'Active Locations', value: activeTargets.length, icon: MapPin, color: 'var(--accent)' },
            { label: 'Active Categories', value: categories.filter(c => c.is_active).length, icon: Target, color: 'var(--accent2)' },
            { label: 'Search Combos', value: totalCombos, icon: Zap, color: 'var(--green)' },
            { label: 'Est. Lead Pool', value: formatLeads(totalEstimated), icon: Globe, color: 'var(--yellow)' },
          ].map((kpi, i) => {
            const Icon = kpi.icon
            return (
              <motion.div
                key={kpi.label}
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.07 }}
                className="rounded-lg border border-border bg-card p-4"
              >
                <div className="flex items-center gap-2 text-xs text-muted-foreground mb-2">
                  <Icon className="h-3.5 w-3.5" style={{ color: kpi.color }} />
                  {kpi.label}
                </div>
                <div className="font-mono text-2xl font-bold"
                     style={{ color: kpi.color }}>
                  {kpi.value}
                </div>
              </motion.div>
            )
          })}
        </div>

        {/* Tabs */}
        <div className="flex gap-1 rounded-lg border border-border bg-card p-1 w-fit">
          {(['locations', 'categories'] as const).map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`rounded-md px-4 py-1.5 text-sm font-medium capitalize transition-all ${
                activeTab === tab
                  ? 'text-[var(--bg)] shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
              style={activeTab === tab ? { backgroundColor: 'var(--accent)' } : {}}
            >
              {tab}
            </button>
          ))}
        </div>

        {/* Locations tab */}
        {activeTab === 'locations' && (
          <div className="flex flex-col gap-4">
            {/* Filter row */}
            <div className="flex flex-wrap items-center gap-3">
              <div className="relative flex-1 min-w-48">
                <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                <input
                  type="text"
                  placeholder="Search locations..."
                  value={searchQuery}
                  onChange={e => setSearchQuery(e.target.value)}
                  className="w-full rounded-lg border border-border bg-card py-2 pl-8 pr-3
                             text-sm outline-none focus:border-[var(--accent)]
                             transition-colors placeholder:text-muted-foreground"
                />
              </div>
              <div className="flex gap-1">
                {(['all', 'state', 'county', 'city', 'zipcode'] as const).map(f => (
                  <button
                    key={f}
                    onClick={() => setFilterType(f)}
                    className={`rounded-md px-3 py-1.5 text-xs font-medium capitalize
                               transition-all ${
                      filterType === f
                        ? 'text-[var(--bg)]'
                        : 'border border-border text-muted-foreground hover:text-foreground'
                    }`}
                    style={filterType === f ? { backgroundColor: 'var(--accent)' } : {}}
                  >
                    {f}
                  </button>
                ))}
              </div>
            </div>

            {/* Target grid */}
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
              <AnimatePresence>
                {filteredTargets.map((target, i) => (
                  <motion.div
                    key={target.id}
                    initial={{ opacity: 0, scale: 0.97 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.95 }}
                    transition={{ delay: i * 0.04 }}
                    className={`rounded-lg border p-4 transition-all ${
                      target.is_active
                        ? 'border-[var(--accent)]/20 bg-[var(--accent)]/5'
                        : 'border-border bg-card opacity-60'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="text-lg">{typeIcon(target.type)}</span>
                        <div className="min-w-0">
                          <div className="font-semibold text-sm truncate">
                            {target.label}
                          </div>
                          <div className="text-xs text-muted-foreground capitalize mt-0.5">
                            {target.type}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-1 shrink-0">
                        <button
                          onClick={() => handleToggleTarget(target.id, target.is_active)}
                          className="rounded p-1 transition-colors hover:bg-white/5"
                          title={target.is_active ? 'Deactivate' : 'Activate'}
                        >
                          {target.is_active
                            ? <ToggleRight className="h-5 w-5" style={{ color: 'var(--accent)' }} />
                            : <ToggleLeft className="h-5 w-5 text-muted-foreground" />
                          }
                        </button>
                        <button
                          onClick={() => handleDeleteTarget(target.id)}
                          className="rounded p-1 text-muted-foreground transition-colors
                                     hover:bg-red-500/10 hover:text-red-400"
                          title="Delete target"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </div>

                    <div className="mt-3 flex items-center justify-between">
                      <span className={`rounded-full border px-2 py-0.5 text-[10px]
                                       font-semibold uppercase tracking-wider
                                       ${priorityBg(target.priority)}`}>
                        <span className={priorityColor(target.priority)}>
                          {target.priority}
                        </span>
                      </span>
                      <div className="text-right">
                        <div className="font-mono text-sm font-bold"
                             style={{ color: 'var(--accent)' }}>
                          ~{formatLeads(target.estimated_leads)}
                        </div>
                        <div className="text-[10px] text-muted-foreground">
                          est. leads
                        </div>
                      </div>
                    </div>
                  </motion.div>
                ))}
              </AnimatePresence>

              {filteredTargets.length === 0 && (
                <div className="col-span-3 flex flex-col items-center justify-center
                               rounded-lg border border-dashed border-border py-16 gap-3">
                  <MapPin className="h-8 w-8 text-muted-foreground" />
                  <p className="text-sm text-muted-foreground">No targets match your filters</p>
                  <button
                    onClick={() => setShowAddModal(true)}
                    className="text-xs font-medium underline underline-offset-2"
                    style={{ color: 'var(--accent)' }}
                  >
                    Add your first target
                  </button>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Categories tab */}
        {activeTab === 'categories' && (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {categories.map((cat, i) => (
              <motion.div
                key={cat.id}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05 }}
                className={`rounded-lg border p-4 transition-all ${
                  cat.is_active
                    ? 'border-[var(--accent2)]/30 bg-[var(--accent2)]/5'
                    : 'border-border bg-card opacity-60'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div>
                    <div className="font-semibold text-sm">{cat.name}</div>
                    <div className="text-xs text-muted-foreground mt-0.5 font-mono">
                      &quot;{cat.keyword}&quot;
                    </div>
                  </div>
                  <button
                    onClick={() => handleToggleCategory(cat.id, cat.is_active)}
                    className="rounded p-1 transition-colors hover:bg-white/5"
                  >
                    {cat.is_active
                      ? <ToggleRight className="h-5 w-5" style={{ color: 'var(--accent2)' }} />
                      : <ToggleLeft className="h-5 w-5 text-muted-foreground" />
                    }
                  </button>
                </div>
                <div className="mt-3 flex items-center justify-between">
                  <div className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                    cat.is_active
                      ? 'bg-[var(--green)]/10 text-[var(--green)]'
                      : 'bg-border text-muted-foreground'
                  }`}>
                    {cat.is_active ? 'Active' : 'Paused'}
                  </div>
                  <div className="font-mono text-sm font-bold"
                       style={{ color: 'var(--accent2)' }}>
                    ~{formatLeads(cat.estimated_volume)}
                    <span className="text-[10px] font-normal text-muted-foreground ml-1">
                      leads
                    </span>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        )}

        {/* Add Target Modal */}
        <AnimatePresence>
          {showAddModal && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-50 flex items-center justify-center p-4"
              style={{ backgroundColor: 'rgba(0,0,0,0.8)' }}
              onClick={e => { if (e.target === e.currentTarget) setShowAddModal(false) }}
            >
              <motion.div
                initial={{ scale: 0.95, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                exit={{ scale: 0.95, opacity: 0 }}
                className="w-full max-w-md rounded-xl border border-border p-6"
                style={{ backgroundColor: 'var(--bg2)' }}
              >
                <h2 className="text-lg font-bold mb-5">Add Scrape Target</h2>

                <div className="flex flex-col gap-4">
                  {/* Type selector */}
                  <div>
                    <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2 block">
                      Target Type
                    </label>
                    <div className="grid grid-cols-4 gap-2">
                      {(['state', 'county', 'city', 'zipcode'] as const).map(t => (
                        <button
                          key={t}
                          onClick={() => setNewType(t)}
                          className={`rounded-lg border py-2 text-xs font-medium capitalize
                                     transition-all ${
                            newType === t
                              ? 'border-[var(--accent)] text-[var(--accent)] bg-[var(--accent)]/10'
                              : 'border-border text-muted-foreground hover:border-white/20'
                          }`}
                        >
                          <div className="text-base mb-1">{typeIcon(t)}</div>
                          {t}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* State selector */}
                  <div>
                    <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2 block">
                      State
                    </label>
                    <select
                      value={newState}
                      onChange={e => setNewState(e.target.value)}
                      className="w-full rounded-lg border border-border bg-[var(--bg3)] px-3 py-2
                                 text-sm outline-none focus:border-[var(--accent)]"
                    >
                      {US_STATES.map(s => (
                        <option key={s.code} value={s.code}>{s.name}</option>
                      ))}
                    </select>
                  </div>

                  {/* Value input */}
                  <div>
                    <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2 block">
                      {newType === 'state' ? 'State Code (e.g. TX)' :
                       newType === 'county' ? 'County Name (e.g. Travis County)' :
                       newType === 'city' ? 'City Name (e.g. Austin)' :
                       'ZIP Code (e.g. 78701)'}
                    </label>
                    <input
                      type="text"
                      value={newValue}
                      onChange={e => setNewValue(e.target.value)}
                      placeholder={
                        newType === 'state' ? 'TX' :
                        newType === 'county' ? 'Travis County' :
                        newType === 'city' ? 'Austin' : '78701'
                      }
                      className="w-full rounded-lg border border-border bg-[var(--bg3)] px-3 py-2
                                 text-sm outline-none focus:border-[var(--accent)]
                                 placeholder:text-muted-foreground"
                    />
                  </div>

                  {/* Display label */}
                  <div>
                    <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2 block">
                      Display Label (optional)
                    </label>
                    <input
                      type="text"
                      value={newLabel}
                      onChange={e => setNewLabel(e.target.value)}
                      placeholder="e.g. Downtown Austin"
                      className="w-full rounded-lg border border-border bg-[var(--bg3)] px-3 py-2
                                 text-sm outline-none focus:border-[var(--accent)]
                                 placeholder:text-muted-foreground"
                    />
                  </div>

                  {/* Priority */}
                  <div>
                    <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2 block">
                      Priority
                    </label>
                    <div className="flex gap-2">
                      {(['high', 'medium', 'low'] as const).map(p => (
                        <button
                          key={p}
                          onClick={() => setNewPriority(p)}
                          className={`flex-1 rounded-lg border py-2 text-xs font-semibold
                                     uppercase tracking-wider transition-all ${
                            newPriority === p ? priorityBg(p) : 'border-border text-muted-foreground'
                          }`}
                        >
                          <span className={newPriority === p ? priorityColor(p) : ''}>{p}</span>
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex gap-3 mt-2">
                    <button
                      onClick={() => setShowAddModal(false)}
                      className="flex-1 rounded-lg border border-border py-2.5 text-sm
                                 font-medium transition-colors hover:bg-white/5"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handleAddTarget}
                      disabled={!newValue.trim()}
                      className="flex-1 rounded-lg py-2.5 text-sm font-semibold
                                 transition-all hover:opacity-80 disabled:opacity-40
                                 disabled:cursor-not-allowed"
                      style={{ backgroundColor: 'var(--accent)', color: 'var(--bg)' }}
                    >
                      Add Target
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
