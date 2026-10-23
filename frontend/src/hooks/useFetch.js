import { useCallback, useEffect, useRef, useState } from 'react'
import { api, errMsg } from '../api'

/** GET helper with loading / error / reload. `params` changes re-trigger the fetch. */
export function useFetch(url, params, { enabled = true, initial = null } = {}) {
  const [data, setData] = useState(initial)
  const [loading, setLoading] = useState(enabled)
  const [error, setError] = useState(null)
  const key = JSON.stringify([url, params])
  const seq = useRef(0)

  const load = useCallback(async () => {
    if (!enabled || !url) return
    const id = ++seq.current
    setLoading(true); setError(null)
    try {
      const { data } = await api.get(url, { params })
      if (id === seq.current) setData(data)
    } catch (e) {
      if (id === seq.current) setError(errMsg(e))
    } finally {
      if (id === seq.current) setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, enabled])

  useEffect(() => { load() }, [load])
  return { data, loading, error, reload: load, setData }
}

export function useDebounced(value, ms = 350) {
  const [v, setV] = useState(value)
  useEffect(() => { const t = setTimeout(() => setV(value), ms); return () => clearTimeout(t) }, [value, ms])
  return v
}
