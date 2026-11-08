import { useEffect, useRef, useState } from 'react'

export const pendingEraseStorageKey = 'showcase-erase-pending'
const retryDelays = [2000, 5000, 15000, 30000]
type PendingErase = {token: string | null; intakeId: number}
type EraseTask = {
  cancelled: boolean
  controller?: AbortController
  retryTimer?: ReturnType<typeof setTimeout>
  deadlineTimer?: ReturnType<typeof setTimeout>
}

function readPending(): PendingErase[] {
  return JSON.parse(sessionStorage.getItem(pendingEraseStorageKey) || '[]')
}

function savePending(pending: PendingErase[]) {
  if (pending.length) sessionStorage.setItem(pendingEraseStorageKey, JSON.stringify(pending))
  else sessionStorage.removeItem(pendingEraseStorageKey)
}

export function usePendingErases() {
  const [pendingErases, setPendingErases] = useState(readPending)
  const tasks = useRef(new Map<string, EraseTask>())

  useEffect(() => {
    for (const pending of pendingErases) {
      const id = JSON.stringify([pending.token, pending.intakeId])
      if (tasks.current.has(id)) continue
      const task: EraseTask = {cancelled: false}
      tasks.current.set(id, task)
      let retries = 0
      async function attempt() {
        const controller = new AbortController()
        task.controller = controller
        let retry = false
        try {
          const deadline = new Promise<never>((_, reject) => {
            task.deadlineTimer = setTimeout(() => {
              controller.abort()
              reject(new TypeError('Erase request timed out'))
            }, 10000)
          })
          const response = await Promise.race([
            fetch(`/api/v1/intake/${pending.intakeId}/end-session`, {
              method: 'POST',
              headers: pending.token ? {Authorization: `Bearer ${pending.token}`} : {},
              signal: controller.signal,
            }),
            deadline,
          ])
          if (task.cancelled) return
          if (response.ok || [401, 404].includes(response.status)) {
            const remaining = readPending().filter(item =>
              item.token !== pending.token || item.intakeId !== pending.intakeId)
            savePending(remaining)
            tasks.current.delete(id)
            setPendingErases(remaining)
          } else {
            retry = [409, 503].includes(response.status)
          }
        } catch {
          retry = true
        } finally {
          clearTimeout(task.deadlineTimer)
        }
        if (retry && !task.cancelled) {
          task.retryTimer = setTimeout(() => void attempt(), retryDelays[Math.min(retries++, retryDelays.length - 1)])
        }
      }
      void attempt()
    }
  }, [pendingErases])

  useEffect(() => {
    const active = tasks.current
    return () => {
      for (const task of active.values()) {
        task.cancelled = true
        clearTimeout(task.retryTimer)
        clearTimeout(task.deadlineTimer)
        task.controller?.abort()
      }
      active.clear()
    }
  }, [])

  function queueErase(pending: PendingErase) {
    const current = readPending()
    if (!current.some(item => item.token === pending.token && item.intakeId === pending.intakeId)) {
      current.push(pending)
    }
    savePending(current)
    setPendingErases(current)
  }

  return {pendingErases, queueErase}
}
