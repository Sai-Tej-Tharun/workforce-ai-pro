import { useEffect, useRef, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard, Users, Building2, Clock, CalendarDays, Wallet, FileText, Star, ListChecks, Brain, ShieldAlert,
  HandHelping, BarChart3, TrendingUp, Lightbulb, Radio, Database, MessageSquare, Bell, FileBarChart, ScrollText,
  UserCog, Menu, LogOut, X, Wifi, WifiOff, KeyRound,
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useApp } from '../context/AppContext'
import { Avatar, cx } from './ui'
import { fmt, api } from '../api'

const A = ['ADMIN'], AH = ['ADMIN', 'HR'], AHM = ['ADMIN', 'HR', 'MANAGER'], ALL = ['ADMIN', 'HR', 'MANAGER', 'EMPLOYEE']
export const NAV = [
  { group: 'Overview', items: [{ to: '/', label: 'Dashboard', icon: LayoutDashboard, roles: ALL }] },
  { group: 'Workforce', items: [
    { to: '/employees', label: 'Employees', icon: Users, roles: ALL },
    { to: '/departments', label: 'Departments & Roles', icon: Building2, roles: AHM },
    { to: '/attendance', label: 'Attendance', icon: Clock, roles: ALL },
    { to: '/leave', label: 'Leave', icon: CalendarDays, roles: ALL },
    { to: '/payroll', label: 'Payroll', icon: Wallet, roles: ALL },
    { to: '/performance', label: 'Performance', icon: Star, roles: ALL },
    { to: '/tasks', label: 'Tasks & Workflow', icon: ListChecks, roles: ALL },
    { to: '/documents', label: 'Documents', icon: FileText, roles: ALL },
  ] },
  { group: 'AI Intelligence', items: [
    { to: '/predictions', label: 'AI Predictions', icon: Brain, roles: AHM },
    { to: '/risk-monitor', label: 'Risk Monitor', icon: ShieldAlert, roles: AHM },
    { to: '/interventions', label: 'Interventions', icon: HandHelping, roles: AHM },
    { to: '/attrition', label: 'Attrition Analytics', icon: BarChart3, roles: AHM },
    { to: '/forecast', label: 'Forecast & Stability', icon: TrendingUp, roles: AH },
    { to: '/recommendations', label: 'Recommendations', icon: Lightbulb, roles: ALL },
    { to: '/live', label: 'Live Workforce Feed', icon: Radio, roles: AHM },
    { to: '/datasets', label: 'Datasets & Models', icon: Database, roles: AH },
  ] },
  { group: 'Communication', items: [
    { to: '/chat', label: 'Chat', icon: MessageSquare, roles: ALL },
    { to: '/notifications', label: 'Notifications', icon: Bell, roles: ALL },
  ] },
  { group: 'Administration', items: [
    { to: '/reports', label: 'Reports & Export', icon: FileBarChart, roles: AHM },
    { to: '/audit', label: 'Audit Logs', icon: ScrollText, roles: AH },
    { to: '/users', label: 'User Management', icon: UserCog, roles: AH },
  ] },
]

function Sidebar({ open, onClose }) {
  const { user } = useAuth()
  return (
    <>
      {open && <div className="fixed inset-0 z-30 bg-slate-900/50 lg:hidden" onClick={onClose} />}
      <aside className={cx('fixed inset-y-0 left-0 z-40 flex w-64 flex-col bg-slate-900 text-slate-300 transition-transform lg:translate-x-0', open ? 'translate-x-0' : '-translate-x-full')}>
        <div className="flex h-16 items-center justify-between px-5">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-sm font-bold text-white">W</div>
            <div className="leading-tight"><div className="text-sm font-semibold text-white">WorkForce AI Pro</div><div className="text-[10px] uppercase tracking-wider text-slate-500">Workforce Intelligence</div></div>
          </div>
          <button className="lg:hidden" onClick={onClose} aria-label="Close menu"><X size={18} /></button>
        </div>
        <nav className="flex-1 overflow-y-auto px-3 pb-6">
          {NAV.map((g) => {
            const items = g.items.filter((i) => i.roles.includes(user.role))
            if (!items.length) return null
            return (
              <div key={g.group} className="mt-4">
                <div className="px-3 pb-1 text-[10px] font-semibold uppercase tracking-wider text-slate-500">{g.group}</div>
                {items.map((i) => (
                  <NavLink key={i.to} to={i.to} end={i.to === '/'} onClick={onClose}
                    className={({ isActive }) => cx('mb-0.5 flex items-center gap-3 rounded-lg px-3 py-2 text-sm', isActive ? 'bg-brand-600 text-white' : 'hover:bg-slate-800 hover:text-white')}>
                    <i.icon size={17} />{i.label}
                  </NavLink>
                ))}
              </div>
            )
          })}
        </nav>
      </aside>
    </>
  )
}

function BellMenu() {
  const { unread, refreshUnread, setUnread } = useApp()
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState([])
  const nav = useNavigate()
  const ref = useRef()
  useEffect(() => {
    const h = (e) => ref.current && !ref.current.contains(e.target) && setOpen(false)
    document.addEventListener('mousedown', h); return () => document.removeEventListener('mousedown', h)
  }, [])
  const toggle = async () => {
    const next = !open; setOpen(next)
    if (next) { const { data } = await api.get('/notifications', { params: { size: 6 } }); setItems(data.items) }
  }
  const readAll = async () => { await api.post('/notifications/read-all'); setUnread(0); setItems((i) => i.map((n) => ({ ...n, is_read: true }))) }
  return (
    <div className="relative" ref={ref}>
      <button onClick={toggle} className="relative rounded-lg p-2 text-slate-500 hover:bg-slate-100" aria-label="Notifications">
        <Bell size={20} />
        {unread > 0 && <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-rose-600 px-1 text-[10px] font-bold text-white">{unread > 99 ? '99+' : unread}</span>}
      </button>
      {open && (
        <div className="absolute right-0 z-50 mt-2 w-80 rounded-xl border border-slate-100 bg-white shadow-xl">
          <div className="flex items-center justify-between border-b border-slate-100 px-4 py-2.5"><span className="text-sm font-semibold">Notifications</span>
            <button onClick={readAll} className="text-xs text-brand-600 hover:underline">Mark all read</button></div>
          <div className="max-h-80 overflow-y-auto">
            {items.length === 0 && <div className="p-6 text-center text-sm text-slate-400">You're all caught up</div>}
            {items.map((n) => (
              <div key={n.id} className={cx('border-b border-slate-50 px-4 py-2.5 text-sm', !n.is_read && 'bg-brand-50/50')}>
                <div className="font-medium text-slate-800">{n.title}</div><div className="line-clamp-2 text-xs text-slate-500">{n.message}</div>
                <div className="mt-0.5 text-[10px] text-slate-400">{fmt.ago(n.created_at)}</div>
              </div>
            ))}
          </div>
          <button onClick={() => { setOpen(false); nav('/notifications'); refreshUnread() }} className="w-full border-t border-slate-100 py-2 text-center text-sm text-brand-600 hover:bg-slate-50">View all</button>
        </div>
      )}
    </div>
  )
}

export default function Layout() {
  const { user, logout } = useAuth()
  const { wsState } = useApp()
  const [open, setOpen] = useState(false)
  const loc = useLocation()
  const nav = useNavigate()
  useEffect(() => setOpen(false), [loc.pathname])
  const current = NAV.flatMap((g) => g.items).find((i) => (i.to === '/' ? loc.pathname === '/' : loc.pathname.startsWith(i.to)))
  return (
    <div className="min-h-screen">
      <Sidebar open={open} onClose={() => setOpen(false)} />
      <div className="lg:pl-64">
        <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b border-slate-200 bg-white/90 px-4 backdrop-blur lg:px-8">
          <div className="flex items-center gap-3">
            <button className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 lg:hidden" onClick={() => setOpen(true)} aria-label="Open menu"><Menu size={20} /></button>
            <div className="text-sm font-medium text-slate-600">{current?.label || 'WorkForce AI Pro'}</div>
          </div>
          <div className="flex items-center gap-3">
            <span className={cx('hidden items-center gap-1 rounded-full px-2 py-1 text-xs sm:flex', wsState === 'live' ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-500')} title="Real-time connection">
              {wsState === 'live' ? <Wifi size={13} /> : <WifiOff size={13} />}{wsState === 'live' ? 'Live' : 'Offline'}
            </span>
            <BellMenu />
            <div className="flex items-center gap-2.5 border-l border-slate-200 pl-3">
              <Avatar name={user.full_name} />
              <div className="hidden text-right leading-tight sm:block"><div className="text-sm font-medium text-slate-800">{user.full_name}</div><div className="text-[11px] uppercase tracking-wide text-slate-400">{user.role}</div></div>
              <button onClick={() => nav('/account')} className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-600" title="Account" aria-label="Account"><KeyRound size={17} /></button>
              <button onClick={logout} className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-rose-600" title="Sign out" aria-label="Sign out"><LogOut size={17} /></button>
            </div>
          </div>
        </header>
        <main className="p-4 lg:p-8"><Outlet /></main>
      </div>
    </div>
  )
}
