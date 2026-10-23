import { useEffect } from 'react'
import { X, Loader2, Inbox, AlertCircle, ChevronLeft, ChevronRight, ArrowUp, ArrowDown } from 'lucide-react'

export const cx = (...a) => a.filter(Boolean).join(' ')

export function Spinner({ className = '' }) { return <Loader2 className={cx('animate-spin text-brand-600', className)} size={20} /> }

export function Loading({ label = 'Loading…' }) {
  return <div className="flex items-center justify-center gap-2 py-16 text-sm text-slate-500"><Spinner />{label}</div>
}

export function Empty({ title = 'Nothing here yet', hint, action }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-14 text-center">
      <Inbox className="text-slate-300" size={40} />
      <div className="font-medium text-slate-600">{title}</div>
      {hint && <div className="max-w-sm text-sm text-slate-400">{hint}</div>}
      {action}
    </div>
  )
}

export function ErrorBox({ error, onRetry }) {
  if (!error) return null
  return (
    <div className="flex items-start gap-2 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700" role="alert">
      <AlertCircle size={18} className="mt-0.5 shrink-0" />
      <div className="flex-1">{error}</div>
      {onRetry && <button onClick={onRetry} className="font-medium underline">Retry</button>}
    </div>
  )
}

export function PageHeader({ title, subtitle, actions }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">{title}</h1>
        {subtitle && <p className="mt-0.5 text-sm text-slate-500">{subtitle}</p>}
      </div>
      <div className="flex flex-wrap items-center gap-2">{actions}</div>
    </div>
  )
}

export function Card({ title, subtitle, actions, children, className = '', pad = true }) {
  return (
    <section className={cx('card', className)}>
      {(title || actions) && (
        <header className="flex items-center justify-between gap-2 border-b border-slate-100 px-5 py-3">
          <div><h2 className="text-sm font-semibold text-slate-800">{title}</h2>{subtitle && <p className="text-xs text-slate-400">{subtitle}</p>}</div>
          <div className="flex items-center gap-2">{actions}</div>
        </header>
      )}
      <div className={pad ? 'p-5' : ''}>{children}</div>
    </section>
  )
}

const TONES = {
  indigo: 'bg-indigo-50 text-indigo-600', emerald: 'bg-emerald-50 text-emerald-600', amber: 'bg-amber-50 text-amber-600',
  rose: 'bg-rose-50 text-rose-600', sky: 'bg-sky-50 text-sky-600', slate: 'bg-slate-100 text-slate-600',
}
export function StatCard({ label, value, hint, icon: Icon, tone = 'indigo' }) {
  return (
    <div className="card flex items-center gap-4 p-4">
      {Icon && <div className={cx('rounded-xl p-3', TONES[tone])}><Icon size={22} /></div>}
      <div className="min-w-0">
        <div className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</div>
        <div className="truncate text-2xl font-semibold text-slate-900">{value ?? '–'}</div>
        {hint && <div className="text-xs text-slate-400">{hint}</div>}
      </div>
    </div>
  )
}

const BADGE = {
  low: 'bg-emerald-100 text-emerald-700', medium: 'bg-amber-100 text-amber-700', high: 'bg-rose-100 text-rose-700',
  critical: 'bg-red-600 text-white', info: 'bg-sky-100 text-sky-700', warning: 'bg-amber-100 text-amber-700',
  active: 'bg-emerald-100 text-emerald-700', terminated: 'bg-slate-200 text-slate-600', on_leave: 'bg-sky-100 text-sky-700',
  pending: 'bg-amber-100 text-amber-700', approved: 'bg-emerald-100 text-emerald-700', rejected: 'bg-rose-100 text-rose-700',
  cancelled: 'bg-slate-200 text-slate-600', open: 'bg-rose-100 text-rose-700', acknowledged: 'bg-amber-100 text-amber-700',
  resolved: 'bg-emerald-100 text-emerald-700', in_progress: 'bg-sky-100 text-sky-700', completed: 'bg-emerald-100 text-emerald-700',
  dismissed: 'bg-slate-200 text-slate-600', todo: 'bg-slate-100 text-slate-700', done: 'bg-emerald-100 text-emerald-700',
  present: 'bg-emerald-100 text-emerald-700', late: 'bg-amber-100 text-amber-700', absent: 'bg-rose-100 text-rose-700',
  half_day: 'bg-sky-100 text-sky-700', paid: 'bg-emerald-100 text-emerald-700', generated: 'bg-sky-100 text-sky-700',
  Stable: 'bg-emerald-100 text-emerald-700', Watch: 'bg-amber-100 text-amber-700', 'At risk': 'bg-rose-100 text-rose-700',
  default: 'bg-slate-100 text-slate-700',
}
export function Badge({ children, tone, className = '' }) {
  const t = tone || String(children)
  return <span className={cx('inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium capitalize', BADGE[t] || BADGE.default, className)}>{String(children).replace(/_/g, ' ')}</span>
}

export function RiskBadge({ level, score }) {
  if (!level) return <span className="text-xs text-slate-400">n/a</span>
  return <Badge tone={level}>{score != null ? `${(score * 100).toFixed(0)}% · ${level}` : level}</Badge>
}

export function RiskBar({ score }) {
  const p = Math.round((score || 0) * 100)
  const c = p >= 60 ? 'bg-rose-500' : p >= 30 ? 'bg-amber-400' : 'bg-emerald-500'
  return (
    <div className="flex items-center gap-2" title={`${p}%`}>
      <div className="h-2 w-24 overflow-hidden rounded-full bg-slate-100"><div className={cx('h-full rounded-full', c)} style={{ width: `${p}%` }} /></div>
      <span className="w-9 text-right text-xs tabular-nums text-slate-600">{p}%</span>
    </div>
  )
}

export function Progress({ value, tone = 'brand' }) {
  const c = { brand: 'bg-brand-600', emerald: 'bg-emerald-500', amber: 'bg-amber-400', rose: 'bg-rose-500' }[tone]
  return <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100"><div className={cx('h-full rounded-full', c)} style={{ width: `${Math.min(100, value || 0)}%` }} /></div>
}

export function Modal({ open, onClose, title, children, wide, footer }) {
  useEffect(() => {
    if (!open) return
    const k = (e) => e.key === 'Escape' && onClose()
    document.addEventListener('keydown', k)
    return () => document.removeEventListener('keydown', k)
  }, [open, onClose])
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-900/50 p-4 pt-12" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div role="dialog" aria-modal="true" className={cx('w-full rounded-xl bg-white shadow-2xl', wide ? 'max-w-4xl' : 'max-w-lg')}>
        <header className="flex items-center justify-between border-b border-slate-100 px-5 py-3.5">
          <h3 className="font-semibold text-slate-900">{title}</h3>
          <button onClick={onClose} className="rounded p-1 text-slate-400 hover:bg-slate-100" aria-label="Close"><X size={18} /></button>
        </header>
        <div className="p-5">{children}</div>
        {footer && <footer className="flex justify-end gap-2 border-t border-slate-100 px-5 py-3">{footer}</footer>}
      </div>
    </div>
  )
}

export function Field({ label, children, hint, error }) {
  return (
    <label className="block">
      {label && <span className="label">{label}</span>}
      {children}
      {hint && !error && <span className="mt-1 block text-xs text-slate-400">{hint}</span>}
      {error && <span className="mt-1 block text-xs text-rose-600">{error}</span>}
    </label>
  )
}
export const Input = (p) => <input {...p} className={cx('input', p.className)} />
export const Select = ({ options = [], placeholder, children, ...p }) => (
  <select {...p} className={cx('input', p.className)}>
    {placeholder !== undefined && <option value="">{placeholder}</option>}
    {options.map((o) => (typeof o === 'object' ? <option key={o.value} value={o.value}>{o.label}</option> : <option key={o} value={o}>{o}</option>))}
    {children}
  </select>
)

export function Tabs({ tabs, value, onChange }) {
  return (
    <div className="mb-4 flex gap-1 overflow-x-auto border-b border-slate-200">
      {tabs.map((t) => (
        <button key={t.value} onClick={() => onChange(t.value)}
          className={cx('whitespace-nowrap border-b-2 px-4 py-2 text-sm font-medium', value === t.value ? 'border-brand-600 text-brand-700' : 'border-transparent text-slate-500 hover:text-slate-700')}>
          {t.label}{t.count != null && <span className="ml-1.5 rounded-full bg-slate-100 px-1.5 text-xs">{t.count}</span>}
        </button>
      ))}
    </div>
  )
}

export function Pagination({ page, size, total, onPage }) {
  const pages = Math.max(1, Math.ceil((total || 0) / size))
  if (!total || pages <= 1) return total ? <div className="px-4 py-2 text-xs text-slate-400">{total} record{total === 1 ? '' : 's'}</div> : null
  return (
    <div className="flex items-center justify-between border-t border-slate-100 px-4 py-2.5 text-sm text-slate-500">
      <span>{(page - 1) * size + 1}–{Math.min(page * size, total)} of {total}</span>
      <div className="flex items-center gap-1">
        <button className="btn-ghost !px-2 !py-1" disabled={page <= 1} onClick={() => onPage(page - 1)} aria-label="Previous page"><ChevronLeft size={16} /></button>
        <span className="px-2">Page {page} / {pages}</span>
        <button className="btn-ghost !px-2 !py-1" disabled={page >= pages} onClick={() => onPage(page + 1)} aria-label="Next page"><ChevronRight size={16} /></button>
      </div>
    </div>
  )
}

/** Advanced table: loading skeleton, empty state, sortable headers, row click, custom cell render. */
export function DataTable({ columns, rows, loading, empty, onRowClick, sort, onSort, rowKey = 'id', dense }) {
  if (loading && !rows?.length) return <Loading />
  if (!rows?.length) return empty || <Empty />
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px]">
        <thead className="bg-slate-50">
          <tr>
            {columns.map((c) => (
              <th key={c.key} className={cx('th', c.className, c.sortKey && onSort && 'cursor-pointer select-none hover:text-slate-700')}
                onClick={() => c.sortKey && onSort?.(c.sortKey)}>
                <span className="inline-flex items-center gap-1">{c.label}
                  {sort && c.sortKey && sort.key === c.sortKey && (sort.order === 'asc' ? <ArrowUp size={12} /> : <ArrowDown size={12} />)}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody className={cx('divide-y divide-slate-100', loading && 'opacity-60')}>
          {rows.map((r, i) => (
            <tr key={r[rowKey] ?? i} onClick={() => onRowClick?.(r)} className={cx('hover:bg-slate-50/70', onRowClick && 'cursor-pointer')}>
              {columns.map((c) => <td key={c.key} className={cx('td', dense && '!py-2', c.className)}>{c.render ? c.render(r) : r[c.key] ?? '–'}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function Confirm({ open, title = 'Are you sure?', message, onCancel, onConfirm, danger = true, busy }) {
  return (
    <Modal open={open} onClose={onCancel} title={title}
      footer={<><button className="btn-ghost" onClick={onCancel}>Cancel</button><button className={danger ? 'btn-danger' : 'btn-primary'} onClick={onConfirm} disabled={busy}>{busy ? 'Working…' : 'Confirm'}</button></>}>
      <p className="text-sm text-slate-600">{message}</p>
    </Modal>
  )
}

export function Avatar({ name = '?', size = 32 }) {
  const initials = name.split(' ').map((s) => s[0]).slice(0, 2).join('').toUpperCase()
  const hue = [...name].reduce((a, c) => a + c.charCodeAt(0), 0) % 360
  return <div className="flex shrink-0 items-center justify-center rounded-full font-semibold text-white" style={{ width: size, height: size, fontSize: size * 0.38, background: `hsl(${hue} 55% 48%)` }}>{initials}</div>
}

export const CHART_COLORS = ['#6366f1', '#10b981', '#f59e0b', '#ef4444', '#0ea5e9', '#8b5cf6', '#14b8a6', '#f97316']
