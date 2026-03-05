"use client"

import { useState, useRef, useEffect } from 'react'
import { Shell } from '@/components/layout/Shell'
import { motion } from 'framer-motion'
import useSWR from 'swr'
import {
  MessageSquare, Search, Send, Bot, User,
  ThumbsUp, ThumbsDown, Minus,
  Clock, Mail, AlertCircle, CheckCircle2, XCircle,
  Sparkles
} from 'lucide-react'
import type { Conversation, ConversationStatus } from '@/lib/types'

const fetcher = (url: string) => fetch(url).then(r => r.json())

const STATUS_CONFIG: Record<ConversationStatus, {
  label: string; color: string; icon: React.ElementType
}> = {
  active:         { label: 'Active',         color: 'var(--green)',  icon: CheckCircle2 },
  replied:        { label: 'Replied',        color: 'var(--accent)', icon: Mail },
  bounced:        { label: 'Bounced',        color: 'var(--red)',    icon: XCircle },
  unsubscribed:   { label: 'Unsubscribed',   color: 'var(--cold)',   icon: XCircle },
  meeting_booked: { label: 'Meeting Booked', color: 'var(--green)',  icon: CheckCircle2 },
  not_interested: { label: 'Not Interested', color: 'var(--red)',    icon: AlertCircle },
  no_reply:       { label: 'No Reply',       color: 'var(--yellow)', icon: Clock },
}

const SENTIMENT_ICON: Record<string, React.ElementType> = {
  positive: ThumbsUp,
  negative: ThumbsDown,
  neutral:  Minus,
}

const SENTIMENT_COLOR: Record<string, string> = {
  positive: 'var(--green)',
  negative: 'var(--red)',
  neutral:  'var(--cold)',
}

function formatTime(ts: string) {
  const d = new Date(ts)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  const hours = Math.floor(diff / 3600000)
  if (hours < 1) return `${Math.floor(diff / 60000)}m ago`
  if (hours < 24) return `${hours}h ago`
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

export default function ConversationsPage() {
  const { data } = useSWR('/api/conversations', fetcher, { refreshInterval: 15000 })
  const conversations: Conversation[] = data?.conversations ?? []
  const stats = data?.stats ?? { total: 0, replied: 0, positive: 0, meeting_booked: 0 }

  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState<ConversationStatus | 'all'>('all')
  const [searchTerm, setSearchTerm] = useState('')
  const [replyText, setReplyText] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const filteredConversations = conversations.filter(c => {
    if (statusFilter !== 'all' && c.status !== statusFilter) return false
    if (searchTerm) {
      const q = searchTerm.toLowerCase()
      return (
        c.contact_name.toLowerCase().includes(q) ||
        c.company_name.toLowerCase().includes(q) ||
        c.email_hook.toLowerCase().includes(q)
      )
    }
    return true
  })

  const selected = conversations.find(c => c.id === selectedId) ?? null

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [selected?.messages.length])

  async function handleSendReply() {
    if (!replyText.trim() || !selectedId) return
    await fetch('/api/conversations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ conversation_id: selectedId, message: replyText.trim() }),
    })
    setReplyText('')
  }

  return (
    <Shell>
      <div className="flex flex-col h-[calc(100vh-4rem)]">

        {/* Header */}
        <div className="shrink-0 border-b border-border px-6 py-4">
          <div className="flex items-start justify-between">
            <div>
              <h1 className="text-2xl font-bold tracking-tight"
                  style={{ fontFamily: 'var(--font-syne)' }}>
                AI Conversations
              </h1>
              <p className="mt-1 text-sm text-muted-foreground">
                Monitor &amp; manage lead email threads
              </p>
            </div>
            <div className="flex gap-3">
              {[
                { label: 'Total', value: stats.total, color: 'var(--accent)' },
                { label: 'Replied', value: stats.replied, color: 'var(--green)' },
                { label: 'Meetings', value: stats.meeting_booked, color: 'var(--accent2)' },
              ].map(s => (
                <div key={s.label} className="rounded-lg border border-border bg-card
                                             px-3 py-2 text-center min-w-[80px]">
                  <div className="text-[10px] text-muted-foreground uppercase tracking-wider">
                    {s.label}
                  </div>
                  <div className="mt-0.5 font-mono text-lg font-bold"
                       style={{ color: s.color }}>{s.value}</div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Split pane */}
        <div className="flex flex-1 overflow-hidden">

          {/* Thread list */}
          <div className="w-[380px] shrink-0 border-r border-border flex flex-col
                          overflow-hidden">
            {/* Search + filter */}
            <div className="shrink-0 p-3 border-b border-border space-y-2">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4
                                   text-muted-foreground" />
                <input type="text" value={searchTerm}
                  onChange={e => setSearchTerm(e.target.value)}
                  placeholder="Search conversations..."
                  className="w-full rounded-lg border border-border bg-[var(--bg3)]
                             pl-9 pr-3 py-2 text-sm outline-none
                             focus:border-[var(--accent)] placeholder:text-muted-foreground" />
              </div>
              <div className="flex gap-1 flex-wrap">
                {(['all', 'active', 'replied', 'bounced', 'unsubscribed', 'meeting_booked', 'not_interested', 'no_reply'] as const).map(
                  status => {
                    const isActive = statusFilter === status
                    const cfg = status === 'all'
                      ? { label: 'All', color: 'var(--accent)' }
                      : { label: STATUS_CONFIG[status].label, color: STATUS_CONFIG[status].color }
                    return (
                      <button key={status}
                        onClick={() => setStatusFilter(status)}
                        className={`rounded-md px-2.5 py-1 text-[11px] font-medium
                                    transition-all ${
                          isActive
                            ? 'text-[var(--bg)] shadow-sm'
                            : 'text-muted-foreground hover:text-foreground bg-white/5'
                        }`}
                        style={isActive ? { backgroundColor: cfg.color } : {}}
                      >
                        {cfg.label}
                        {status === 'all'
                          ? ` (${conversations.length})`
                          : ` (${conversations.filter(c => c.status === status).length})`}
                      </button>
                    )
                  }
                )}
              </div>
            </div>

            {/* Thread items */}
            <div className="flex-1 overflow-y-auto">
              {filteredConversations.length === 0 && (
                <div className="flex flex-col items-center justify-center h-full
                                text-muted-foreground gap-2">
                  <MessageSquare className="h-8 w-8 opacity-40" />
                  <span className="text-sm">No conversations</span>
                </div>
              )}
              {filteredConversations.map(conv => {
                const isSelected = conv.id === selectedId
                const statusCfg = STATUS_CONFIG[conv.status]
                const lastMsg = conv.messages[conv.messages.length - 1]
                const lastSentiment = lastMsg?.sentiment ?? 'neutral'
                const SentIcon = SENTIMENT_ICON[lastSentiment] ?? Minus
                const sentColor = SENTIMENT_COLOR[lastSentiment] ?? 'var(--cold)'

                return (
                  <motion.button key={conv.id}
                    layout
                    onClick={() => setSelectedId(conv.id)}
                    className={`w-full text-left p-3 border-b border-border transition-all ${
                      isSelected
                        ? 'bg-[var(--accent)]/10 border-l-2 border-l-[var(--accent)]'
                        : 'hover:bg-white/5'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-sm truncate">
                            {conv.contact_name}
                          </span>
                          <SentIcon className="h-3 w-3 shrink-0"
                                    style={{ color: sentColor }} />
                        </div>
                        <div className="text-[11px] text-muted-foreground truncate mt-0.5">
                          {conv.company_name} — {conv.contact_title}
                        </div>
                      </div>
                      <div className="shrink-0 flex flex-col items-end gap-1">
                        <span className="text-[10px] text-muted-foreground whitespace-nowrap">
                          {formatTime(conv.last_activity_at)}
                        </span>
                        <span className="rounded px-1.5 py-0.5 text-[10px] font-medium"
                              style={{
                                backgroundColor: `${statusCfg.color}20`,
                                color: statusCfg.color,
                              }}>
                          {statusCfg.label}
                        </span>
                      </div>
                    </div>
                    <div className="mt-1.5 text-xs text-muted-foreground truncate">
                      {conv.email_hook}
                    </div>
                    {lastMsg && (
                      <div className="mt-1 text-[11px] text-muted-foreground/70 truncate">
                        {lastMsg.direction === 'outbound' ? 'You: ' : ''}{lastMsg.body.slice(0, 80)}
                      </div>
                    )}
                  </motion.button>
                )
              })}
            </div>
          </div>

          {/* Conversation detail */}
          <div className="flex-1 flex flex-col overflow-hidden">
            {!selected ? (
              <div className="flex-1 flex flex-col items-center justify-center
                              text-muted-foreground gap-3">
                <MessageSquare className="h-12 w-12 opacity-30" />
                <p className="text-sm">Select a conversation to view</p>
              </div>
            ) : (
              <>
                {/* Conv header */}
                <div className="shrink-0 border-b border-border px-6 py-3 flex items-center
                                justify-between">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <h2 className="font-semibold truncate">{selected.email_hook}</h2>
                      <span className="rounded px-2 py-0.5 text-[10px] font-medium"
                            style={{
                              backgroundColor: `${STATUS_CONFIG[selected.status].color}20`,
                              color: STATUS_CONFIG[selected.status].color,
                            }}>
                        {STATUS_CONFIG[selected.status].label}
                      </span>
                    </div>
                    <div className="text-xs text-muted-foreground mt-0.5">
                      {selected.contact_name} ({selected.contact_email}) — {selected.company_name}
                    </div>
                  </div>
                  <div className="shrink-0 flex items-center gap-3">
                    <div className="flex items-center gap-1.5 text-xs">
                      <Sparkles className="h-3.5 w-3.5" style={{ color: 'var(--accent2)' }} />
                      <span className="font-mono font-bold"
                            style={{ color: 'var(--accent2)' }}>
                        {selected.ai_score}
                      </span>
                      <span className="text-muted-foreground">AI score</span>
                    </div>
                  </div>
                </div>

                {/* Messages */}
                <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
                  {selected.messages.map((msg, idx) => {
                    const isOutbound = msg.direction === 'outbound'
                    const SentIcon = SENTIMENT_ICON[msg.sentiment ?? 'neutral'] ?? Minus
                    const sentColor = SENTIMENT_COLOR[msg.sentiment ?? 'neutral'] ?? 'var(--cold)'

                    return (
                      <motion.div key={msg.id}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: idx * 0.04 }}
                        className={`flex ${isOutbound ? 'justify-end' : 'justify-start'}`}
                      >
                        <div className={`max-w-[70%] rounded-xl px-4 py-3 ${
                          isOutbound
                            ? 'bg-[var(--accent)]/15 border border-[var(--accent)]/20'
                            : 'bg-card border border-border'
                        }`}>
                          <div className="flex items-center gap-2 mb-1.5">
                            {isOutbound
                              ? <Bot className="h-3.5 w-3.5" style={{ color: 'var(--accent)' }} />
                              : <User className="h-3.5 w-3.5 text-muted-foreground" />
                            }
                            <span className="text-[11px] font-semibold">
                              {isOutbound ? 'AI Agent' : selected.contact_name}
                            </span>
                            <span className="text-[10px] text-muted-foreground ml-auto">
                              {formatTime(msg.sent_at)}
                            </span>
                          </div>
                          <p className="text-sm leading-relaxed">{msg.body}</p>

                          {/* AI analysis */}
                          {msg.ai_analysis && (
                            <div className="mt-2 rounded-lg bg-black/20 p-2 text-[11px]
                                            text-muted-foreground space-y-1">
                              <div className="flex items-center gap-1.5 font-semibold"
                                   style={{ color: 'var(--accent2)' }}>
                                <Sparkles className="h-3 w-3" />
                                AI Analysis
                              </div>
                              <div className="text-foreground">{msg.ai_analysis}</div>
                            </div>
                          )}

                          <div className="mt-1.5 flex items-center gap-2">
                            <SentIcon className="h-3 w-3" style={{ color: sentColor }} />
                            <span className="text-[10px] capitalize"
                                  style={{ color: sentColor }}>{msg.sentiment}</span>
                          </div>
                        </div>
                      </motion.div>
                    )
                  })}
                  <div ref={messagesEndRef} />
                </div>

                {/* Reply box */}
                <div className="shrink-0 border-t border-border p-4">
                  <div className="flex gap-3">
                    <input type="text" value={replyText}
                      onChange={e => setReplyText(e.target.value)}
                      onKeyDown={e => e.key === 'Enter' && handleSendReply()}
                      placeholder="Type a reply or AI suggestion..."
                      className="flex-1 rounded-lg border border-border bg-[var(--bg3)]
                                 px-4 py-2.5 text-sm outline-none
                                 focus:border-[var(--accent)]
                                 placeholder:text-muted-foreground" />
                    <button onClick={handleSendReply}
                      disabled={!replyText.trim()}
                      className="rounded-lg px-5 py-2.5 text-sm font-semibold
                                 transition-all hover:opacity-80 active:scale-95
                                 disabled:opacity-40"
                      style={{ backgroundColor: 'var(--accent)', color: 'var(--bg)' }}
                    >
                      <Send className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </Shell>
  )
}
