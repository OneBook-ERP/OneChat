import { defineStore } from 'pinia'
import { ref } from 'vue'
import { call } from 'frappe-ui'
import { useSocket } from '@/data/socket'

const METHOD = 'onechat.workspace.notifications.'

export const useNotificationFeed = defineStore('notificationFeed', () => {
  const items = ref([])
  const unread = ref(0)
  const tab = ref('unread')
  const loading = ref(false)
  const loaded = ref(false)
  let listening = false
  let ticket = 0

  async function load() {
    const current = ++ticket
    loading.value = true
    try {
      const data = await call(`${METHOD}feed`, { unread: tab.value === 'unread' ? 1 : 0 })
      if (current !== ticket) return
      items.value = data.items
      unread.value = data.unread
      loaded.value = true
    } finally {
      if (current === ticket) loading.value = false
    }
  }

  async function refreshCount() {
    try {
      unread.value = await call(`${METHOD}count`)
    } catch {
      return
    }
  }

  function setTab(value) {
    tab.value = value
    load()
  }

  async function markRead(item) {
    if (item.read) return
    item.read = 1
    unread.value = Math.max(0, unread.value - 1)
    try {
      unread.value = await call(`${METHOD}mark_read`, { names: JSON.stringify([item.name]) })
    } catch {
      item.read = 0
    }
  }

  async function markAll() {
    items.value.forEach((item) => (item.read = 1))
    unread.value = await call(`${METHOD}mark_read`)
    if (tab.value === 'unread') items.value = []
  }

  function start() {
    if (listening) return
    listening = true
    refreshCount()
    useSocket().on('notification', () => {
      refreshCount()
      if (loaded.value) load()
    })
  }

  return { items, unread, tab, loading, loaded, load, refreshCount, setTab, markRead, markAll, start }
})
