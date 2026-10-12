import { nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { PAGE_SIZES, pageLength } from '@/utils/paging'

function encode(value) {
  if (value === null || value === undefined || value === '') return undefined
  if (typeof value === 'boolean') return value ? '1' : '0'
  return String(value)
}

function decode(raw, fallback) {
  const text = Array.isArray(raw) ? raw[0] : raw
  if (text === undefined || text === null || text === '') return fallback
  if (typeof fallback === 'number') {
    const value = Number(text)
    return Number.isFinite(value) ? value : fallback
  }
  if (typeof fallback === 'boolean') return text === '1' || text === 'true'
  return text
}

export function field(key, source, prop, fallback) {
  return {
    key,
    fallback: fallback === undefined ? source[prop] : fallback,
    get: () => source[prop],
    set: (value) => (source[prop] = value),
  }
}

export function refField(key, target, fallback) {
  return {
    key,
    fallback: fallback === undefined ? target.value : fallback,
    get: () => target.value,
    set: (value) => (target.value = value),
  }
}

export function useQueryState(fields, { size = false } = {}) {
  const route = useRoute()
  const router = useRouter()
  const home = route.name
  let restoring = false
  let written = null

  function read() {
    restoring = true
    for (const item of fields) {
      const next = decode(route.query[item.key], item.fallback)
      if (encode(item.get()) !== encode(next)) item.set(next)
    }
    if (size) {
      const wanted = Number(route.query.size)
      const next = PAGE_SIZES.includes(wanted) ? wanted : PAGE_SIZES[0]
      if (route.query.size !== undefined && pageLength.value !== next) pageLength.value = next
    }
    nextTick(() => (restoring = false))
  }

  function write() {
    if (restoring || route.name !== home) return
    const query = { ...route.query }
    for (const item of fields) {
      const value = encode(item.get())
      if (value === undefined || value === encode(item.fallback)) delete query[item.key]
      else query[item.key] = value
    }
    if (size) {
      if (pageLength.value === PAGE_SIZES[0]) delete query.size
      else query.size = String(pageLength.value)
    }
    const next = JSON.stringify(query)
    if (next === JSON.stringify(route.query)) return
    written = next
    router.replace({ query })
  }

  read()
  watch(() => fields.map((item) => encode(item.get())), write, { flush: 'post' })
  if (size) watch(pageLength, write, { flush: 'post' })
  watch(
    () => route.query,
    (query) => {
      if (route.name !== home) return
      if (written && JSON.stringify(query) === written) return
      written = null
      read()
    },
  )

  return { restoring: () => restoring }
}
