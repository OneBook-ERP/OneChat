<template>
  <CommandPalette v-model:open="open" v-model:query="query" :filterable="false" :title="__('Search')" @select="select">
    <template #default="{ empty }">
      <CommandPaletteInput :placeholder="__('Search contacts, messages, notes and pages')">
        <template #suffix>
          <Spinner v-if="loading" class="size-4 shrink-0 text-ink-gray-5" />
        </template>
      </CommandPaletteInput>

      <p v-if="error" class="px-4.5 pt-3 text-sm text-ink-red-3">{{ error }}</p>

      <ScrollArea viewport-class="max-h-[calc(60vh-7rem)] overscroll-contain">
        <CommandPaletteList class="!overflow-visible">
          <CommandPaletteGroup v-for="group in groups" :key="group.key" :label="group.label">
            <CommandPaletteItem v-for="item in group.items" :key="item.key" :value="item" :label="item.title">
              <template #prefix>
                <span :class="item.icon" class="mr-3 size-4 shrink-0 text-ink-gray-5" aria-hidden="true" />
              </template>

              <span class="flex min-w-0 flex-col">
                <span class="truncate">
                  <Highlight :text="item.title" :query="item.highlight ? text : ''" />
                </span>
                <span v-if="item.subtitle" class="truncate text-sm font-normal text-ink-gray-5">
                  <Highlight :text="item.subtitle" :query="item.highlight ? text : ''" />
                </span>
              </span>

              <template v-if="item.meta" #suffix>
                <span class="text-sm font-normal text-ink-gray-5">{{ item.meta }}</span>
              </template>
            </CommandPaletteItem>
          </CommandPaletteGroup>
        </CommandPaletteList>
      </ScrollArea>

      <div v-if="loading && empty" class="px-4.5 py-8 text-center text-base text-ink-gray-5">
        {{ __('Searching…') }}
      </div>

      <CommandPaletteEmpty v-else-if="!loading">
        {{ text ? __('Nothing matches "{0}"').format(text) : __('Type to search') }}
      </CommandPaletteEmpty>

      <CommandPaletteFooter class="hidden sm:flex">
        <span class="flex items-center gap-1.5">
          <KeyboardShortcut combo="ArrowUp" bg />
          <KeyboardShortcut combo="ArrowDown" bg />
          {{ __('to move') }}
        </span>
        <span class="flex items-center gap-1.5">
          <KeyboardShortcut combo="Enter" bg />
          {{ __('to open') }}
        </span>
        <span class="flex items-center gap-1.5">
          <KeyboardShortcut combo="Escape" bg />
          {{ __('to close') }}
        </span>
      </CommandPaletteFooter>
    </template>
  </CommandPalette>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { KeyboardShortcut, ScrollArea, Spinner, debounce } from 'frappe-ui'
import {
  CommandPalette,
  CommandPaletteEmpty,
  CommandPaletteFooter,
  CommandPaletteGroup,
  CommandPaletteInput,
  CommandPaletteItem,
  CommandPaletteList,
} from 'frappe-ui/experimental'
import Highlight from './Highlight.vue'
import { MIN_QUERY, clearSearches, recentSearches, rememberSearch, searchEverything, searchPages } from '@/data/search'
import { session } from '@/data/session'
import { useUI } from '@/stores/ui'
import { errorMessage, shortTime } from '@/utils/format'
import { translate as __ } from '@/translation'

const open = defineModel('open', { type: Boolean, default: false })

const router = useRouter()
const ui = useUI()

const query = ref('')
const results = ref(null)
const loading = ref(false)
const error = ref('')

const text = computed(() => query.value.trim())

let ticket = 0

const fetchSoon = debounce(async (value, id) => {
  try {
    const data = await searchEverything(value)
    if (id === ticket) results.value = data
  } catch (err) {
    if (id === ticket) {
      results.value = null
      error.value = errorMessage(err)
    }
  } finally {
    if (id === ticket) loading.value = false
  }
}, 250)

watch(text, (value) => {
  ticket += 1
  error.value = ''

  if (value.length < MIN_QUERY) {
    results.value = null
    loading.value = false
    return
  }

  loading.value = true
  fetchSoon(value, ticket)
})

const pages = computed(() =>
  searchPages(session.user.is_admin).map((page) => ({
    key: `page-${page.section}-${page.label}`,
    kind: 'page',
    icon: page.icon,
    title: __(page.label),
    subtitle: page.label === page.section ? '' : __(page.section),
    to: page.to,
  })),
)

const matchingPages = computed(() => {
  const needle = text.value.toLowerCase()
  if (!needle) return pages.value

  return pages.value
    .filter((page) => `${page.title} ${page.subtitle}`.toLowerCase().includes(needle))
    .map((page) => ({ ...page, highlight: true }))
    .slice(0, 6)
})

const groups = computed(() => {
  const out = []
  const data = results.value

  function add(key, label, rows, build) {
    if (rows?.length) out.push({ key, label, items: rows.map((row) => ({ highlight: true, ...build(row) })) })
  }

  if (!text.value && recentSearches.value.length) {
    out.push({
      key: 'recent',
      label: __('Recent searches'),
      items: [
        ...recentSearches.value.map((entry) => ({
          key: `recent-${entry}`,
          kind: 'recent',
          icon: 'lucide-history',
          title: entry,
          query: entry,
        })),
        { key: 'recent-clear', kind: 'clear', icon: 'lucide-x', title: __('Clear recent searches') },
      ],
    })
  }

  if (data) {
    add('contacts', __('Contacts'), data.contacts, (row) => ({
      key: `contact-${row.name}`,
      icon: 'lucide-user',
      title: row.title,
      subtitle: row.subtitle,
      to: { name: 'Inbox', params: { contact: row.name } },
    }))

    add('messages', __('Messages'), data.messages, (row) => ({
      key: `message-${row.name}`,
      icon: row.type === 'Incoming' ? 'lucide-message-square' : 'lucide-message-square-reply',
      title: row.contact_name,
      subtitle: row.snippet,
      meta: shortTime(row.creation),
      to: { name: 'Inbox', params: { contact: row.whatsapp_contact } },
    }))

    add('notes', __('Notes'), data.notes, (row) => ({
      key: `note-${row.name}`,
      icon: 'lucide-notebook-pen',
      title: row.title,
      subtitle: row.snippet,
      to: { name: 'Notes' },
    }))

    add('templates', __('Templates'), data.templates, (row) => ({
      key: `template-${row.name}`,
      icon: 'lucide-layout-template',
      title: row.title,
      subtitle: row.subtitle,
      meta: row.status ? __(row.status.charAt(0) + row.status.slice(1).toLowerCase()) : '',
      to: { name: 'Templates' },
    }))

    add('quick_replies', __('Quick replies'), data.quick_replies, (row) => ({
      key: `quick-reply-${row.name}`,
      icon: 'lucide-zap',
      title: row.title,
      subtitle: [row.shortcut ? `/${row.shortcut.replace(/^\//, '')}` : '', row.snippet].filter(Boolean).join(' · '),
      settings: 'quick-replies',
    }))
  }

  if (matchingPages.value.length) out.push({ key: 'pages', label: __('Go to'), items: matchingPages.value })

  return out
})

function select(item, event) {
  if (item.kind === 'recent') {
    event.preventDefault()
    query.value = item.query
    return
  }

  if (item.kind === 'clear') {
    event.preventDefault()
    clearSearches()
    return
  }

  rememberSearch(text.value)

  if (item.settings) ui.openSettings(item.settings)
  else router.push(item.to)
}
</script>
