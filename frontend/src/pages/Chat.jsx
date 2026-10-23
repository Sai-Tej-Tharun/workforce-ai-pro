import { useEffect, useRef, useState } from 'react'
import { Send, Check, CheckCheck } from 'lucide-react'
import { api, errMsg, fmt } from '../api'
import { useAuth } from '../context/AuthContext'
import { useApp, useLive } from '../context/AppContext'
import { useFetch } from '../hooks/useFetch'
import { Avatar, Badge, Empty, Loading, cx } from '../components/ui'

export default function Chat() {
  const { user } = useAuth()
  const { toast, wsState } = useApp()
  const contacts = useFetch('/chat/contacts')
  const [peer, setPeer] = useState(null)
  const [msgs, setMsgs] = useState([])
  const [text, setText] = useState('')
  const [loading, setLoading] = useState(false)
  const [typing, setTyping] = useState(false)
  const bottom = useRef()
  const peerRef = useRef(null)
  peerRef.current = peer

  const open = async (c) => {
    setPeer(c); setLoading(true)
    try {
      const { data } = await api.get(`/chat/history/${c.id}`)
      setMsgs(data)
      await api.post(`/chat/read/${c.id}`)
      contacts.setData((list) => list?.map((x) => (x.id === c.id ? { ...x, unread: 0 } : x)))
    } finally { setLoading(false) }
  }
  useEffect(() => { bottom.current?.scrollIntoView({ behavior: 'smooth' }) }, [msgs, typing])

  useLive(['chat'], async ({ data }) => {
    if (peerRef.current?.id === data.sender_id) {
      setMsgs((m) => [...m, data]); api.post(`/chat/read/${data.sender_id}`).catch(() => {})
    } else {
      contacts.setData((list) => list?.map((x) => (x.id === data.sender_id ? { ...x, unread: x.unread + 1 } : x)))
    }
  })
  useLive(['chat_read'], ({ data }) => setMsgs((m) => m.map((x) => (data.message_ids.includes(x.id) ? { ...x, is_read: true, read_at: data.read_at } : x))))
  useLive(['typing'], ({ data }) => { if (peerRef.current?.id === data.user_id) { setTyping(true); setTimeout(() => setTyping(false), 2000) } })

  const send = async (e) => {
    e.preventDefault()
    const content = text.trim(); if (!content || !peer) return
    setText('')
    try { const { data } = await api.post('/chat', { receiver_id: peer.id, content }); setMsgs((m) => [...m, data]) } catch (x) { toast(errMsg(x), 'error'); setText(content) }
  }

  return (
    <div className="card flex h-[calc(100vh-9rem)] overflow-hidden">
      <aside className="w-72 shrink-0 overflow-y-auto border-r border-slate-100">
        <div className="border-b border-slate-100 px-4 py-3 text-sm font-semibold">Conversations</div>
        {contacts.loading && !contacts.data ? <Loading /> : contacts.data?.map((c) => (
          <button key={c.id} onClick={() => open(c)} className={cx('flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-slate-50', peer?.id === c.id && 'bg-brand-50')}>
            <div className="relative"><Avatar name={c.full_name} />{c.online && <span className="absolute -bottom-0.5 -right-0.5 h-3 w-3 rounded-full border-2 border-white bg-emerald-500" />}</div>
            <div className="min-w-0 flex-1"><div className="truncate text-sm font-medium">{c.full_name}</div><div className="text-xs uppercase text-slate-400">{c.role}</div></div>
            {c.unread > 0 && <span className="rounded-full bg-brand-600 px-2 py-0.5 text-xs font-semibold text-white">{c.unread}</span>}
          </button>))}
      </aside>
      <section className="flex min-w-0 flex-1 flex-col">
        {!peer ? <div className="flex flex-1 items-center justify-center"><Empty title="Select a conversation" hint={wsState === 'live' ? 'Messages are delivered in real time.' : 'Realtime connection is offline – reconnecting…'} /></div> : <>
          <header className="flex items-center gap-3 border-b border-slate-100 px-5 py-3"><Avatar name={peer.full_name} /><div><div className="font-medium">{peer.full_name}</div><div className="text-xs text-slate-400">{typing ? 'typing…' : peer.role}</div></div></header>
          <div className="flex-1 space-y-2 overflow-y-auto bg-slate-50/60 p-5">
            {loading ? <Loading /> : msgs.length === 0 ? <Empty title="No messages yet" hint="Say hello 👋" /> : msgs.map((m) => {
              const mine = m.sender_id === user.id
              return (<div key={m.id} className={cx('flex', mine ? 'justify-end' : 'justify-start')}>
                <div className={cx('max-w-[70%] rounded-2xl px-3.5 py-2 text-sm shadow-sm', mine ? 'rounded-br-sm bg-brand-600 text-white' : 'rounded-bl-sm bg-white text-slate-800')}>
                  <div className="whitespace-pre-wrap break-words">{m.content}</div>
                  <div className={cx('mt-1 flex items-center justify-end gap-1 text-[10px]', mine ? 'text-indigo-200' : 'text-slate-400')}>{new Date(m.created_at + 'Z').toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    {mine && (m.is_read ? <CheckCheck size={13} className="text-sky-300" aria-label="Read" /> : <Check size={13} aria-label="Sent" />)}</div></div></div>)
            })}
            <div ref={bottom} />
          </div>
          <form onSubmit={send} className="flex gap-2 border-t border-slate-100 p-3">
            <input className="input" placeholder="Type a message…" maxLength={4000} value={text} onChange={(e) => setText(e.target.value)} />
            <button className="btn-primary" disabled={!text.trim()}><Send size={16} />Send</button></form></>}
      </section>
    </div>
  )
}
