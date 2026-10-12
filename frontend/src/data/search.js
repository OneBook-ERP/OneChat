import { ref } from 'vue'
import { call } from 'frappe-ui'
import { SECTIONS } from '@/data/navigation'

const RECENT_KEY = 'onechat.search.recent'
const RECENT_LIMIT = 6

export const MIN_QUERY = 2

export const recentSearches = ref(readRecent())

function readRecent() {
  try {
    const value = JSON.parse(localStorage.getItem(RECENT_KEY) || '[]')

    return Array.isArray(value) ? value.filter((entry) => typeof entry === 'string').slice(0, RECENT_LIMIT) : []
  } catch {
    return []
  }
}

function writeRecent(entries) {
  recentSearches.value = entries

  try {
    localStorage.setItem(RECENT_KEY, JSON.stringify(entries))
  } catch {
    return
  }
}

export function rememberSearch(query) {
  const text = (query || '').trim()
  if (text.length < MIN_QUERY) return

  const rest = recentSearches.value.filter((entry) => entry.toLowerCase() !== text.toLowerCase())
  writeRecent([text, ...rest].slice(0, RECENT_LIMIT))
}

export function clearSearches() {
  writeRecent([])
}

export function searchEverything(query, limit = 5) {
  return call('onechat.workspace.search.search', { query, limit })
}

export function searchPages(isAdmin) {
  const out = []

  for (const section of SECTIONS) {
    if (section.admin && !isAdmin) continue

    for (const group of section.groups) {
      for (const item of group.items) {
        out.push({ label: item.label, icon: item.icon, to: item.to, section: section.label })
      }
    }
  }

  return out
}
