import { defineStore } from 'pinia'
import { ref } from 'vue'
import { COUNTRIES, defaultCountry } from '@/data/countries'

const CACHE = 'onechat-flags-v1'
const BASE = 'https://flagcdn.com/w40/'
const PARALLEL = 6

function keyOf(iso) {
  return String(iso || '').toLowerCase()
}

function remote(key) {
  return `${BASE}${key}.png`
}

function idle(callback) {
  if ('requestIdleCallback' in window) window.requestIdleCallback(callback, { timeout: 4000 })
  else setTimeout(callback, 1500)
}

export const useFlags = defineStore('flags', () => {
  const urls = ref({})
  const warmed = ref(false)
  const pending = new Map()
  let cachePromise = null

  function url(iso) {
    const key = keyOf(iso)
    return urls.value[key] || remote(key)
  }

  function openCache() {
    if (!cachePromise) {
      cachePromise = (async () => {
        try {
          return 'caches' in window ? await caches.open(CACHE) : null
        } catch {
          return null
        }
      })()
    }
    return cachePromise
  }

  async function fetchFlag(key) {
    const address = remote(key)
    const cache = await openCache()
    let response = cache ? await cache.match(address).catch(() => null) : null
    if (!response) {
      response = await fetch(address, { mode: 'cors', credentials: 'omit' })
      if (!response.ok) throw new Error(`Flag ${key} returned ${response.status}`)
      if (cache) await cache.put(address, response.clone()).catch(() => {})
    }
    urls.value[key] = URL.createObjectURL(await response.blob())
  }

  function load(iso) {
    const key = keyOf(iso)
    if (!key || urls.value[key]) return Promise.resolve()
    if (!pending.has(key)) {
      pending.set(
        key,
        fetchFlag(key)
          .catch(() => {})
          .finally(() => pending.delete(key)),
      )
    }
    return pending.get(key)
  }

  function warm() {
    if (warmed.value) return
    warmed.value = true
    load(defaultCountry()?.iso)
    if (navigator.connection?.saveData) return

    idle(async () => {
      const queue = COUNTRIES.map((country) => keyOf(country.iso)).filter((key) => !urls.value[key])
      const worker = async () => {
        while (queue.length) await load(queue.shift())
      }
      await Promise.all(Array.from({ length: PARALLEL }, worker))
    })
  }

  return { urls, warmed, url, load, warm }
})
