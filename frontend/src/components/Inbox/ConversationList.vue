<template>
  <div class="flex min-h-0 flex-col">
    <div class="flex shrink-0 items-center gap-1.5 px-3 pb-2 pt-3">
      <FormControl
        v-model="query"
        class="min-w-0 flex-1"
        type="search"
        :size="compact ? 'lg' : 'sm'"
        :placeholder="channels.length > 1 ? __('Search name, number, email or @username') : __('Search name, number or email')"
      >
        <template #prefix>
          <span class="lucide-search size-4 text-ink-gray-5" aria-hidden="true" />
        </template>
      </FormControl>
      <Button
        :variant="selecting ? 'subtle' : 'ghost'"
        :size="compact ? 'lg' : 'sm'"
        icon="lucide-list-checks"
        :label="selecting ? __('Stop selecting') : __('Select conversations')"
        :tooltip="selecting ? __('Stop selecting') : __('Select conversations')"
        :disabled="!inbox.rows.length && !selecting"
        @click="toggleSelecting"
      />
    </div>

    <ScrollArea ref="scrollArea" class="min-h-0 flex-1" :viewport-class="compact ? 'px-1 pb-4' : 'px-1.5 pb-4'">
      <ListSkeleton v-if="!inbox.loaded && inbox.loading" :rows="8" class="px-1.5" />

      <div v-else-if="inbox.error && !inbox.rows.length" class="px-1.5 pt-2">
        <EmptyState compact icon="lucide-cloud-off" :title="__('Could not load conversations')" :description="inbox.error">
          <Button variant="subtle" :label="__('Try again')" @click="loadConversations()" />
        </EmptyState>
      </div>

      <div v-else-if="!inbox.rows.length" class="px-1.5 pt-2">
        <EmptyState compact :icon="empty.icon" :title="empty.title" :description="empty.description">
          <Button v-if="inbox.search" variant="subtle" :label="__('Clear search')" @click="query = ''" />
        </EmptyState>
      </div>

      <template v-else>
        <nav class="flex flex-col gap-0.5" :aria-label="__('Conversations')">
          <ConversationRow
            v-for="row in inbox.rows"
            :key="row.name"
            :row="row"
            :active="row.name === active"
            :compact="compact"
            :selectable="selecting"
            :selected="picked.has(row.name)"
            @toggle="pick(row.name)"
          />
        </nav>

        <div ref="sentinel" class="flex h-12 items-center justify-center">
          <Spinner v-if="inbox.loading" class="size-4 text-ink-gray-5" />
          <Button v-else-if="inbox.hasMore" variant="ghost" size="sm" :label="__('Load more')" @click="loadMoreConversations" />
        </div>
      </template>
    </ScrollArea>

    <div v-if="selecting" class="flex shrink-0 items-center gap-1 border-t border-outline-gray-2 bg-surface-base px-2 py-1.5">
      <p class="min-w-0 flex-1 truncate pl-1 text-sm text-ink-gray-7">{{ __('{0} selected').format(picked.size) }}</p>
      <Dropdown :options="assignOptions" side="top" align="end" :disabled="!picked.size || busy">
        <Button variant="ghost" icon="lucide-user-check" :label="__('Assign')" :tooltip="__('Assign')" :disabled="!picked.size || busy" />
      </Dropdown>
      <Dropdown :options="labelOptions" side="top" align="end" :disabled="!picked.size || busy || !labelOptions.length">
        <Button
          variant="ghost"
          icon="lucide-tag"
          :label="__('Label')"
          :tooltip="__('Label')"
          :disabled="!picked.size || busy || !labelOptions.length"
        />
      </Dropdown>
      <Dropdown :options="statusOptions" side="top" align="end" :disabled="!picked.size || busy">
        <Button variant="ghost" icon="lucide-circle-check" :label="__('Status')" :tooltip="__('Status')" :disabled="!picked.size || busy" />
      </Dropdown>
      <Button
        variant="ghost"
        icon="lucide-mail-open"
        :label="__('Mark read')"
        :tooltip="__('Mark read')"
        :disabled="!picked.size || busy"
        @click="apply('read')"
      />
      <Button
        variant="ghost"
        size="sm"
        :label="allPicked ? __('Clear') : __('All')"
        :tooltip="allPicked ? __('Clear selection') : __('Select all')"
        @click="pickAll"
      />
      <Button variant="ghost" icon="lucide-x" :label="__('Cancel')" :tooltip="__('Stop selecting')" @click="toggleSelecting" />
    </div>
    <ResolveDialog
      v-model:open="resolving"
      :rules="rules"
      :waiting="rules.when_waiting !== 'Allow'"
      :count="picked.size"
      :busy="busy"
      @confirm="(extra) => apply('status', 'Resolved', extra)"
    />
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Button, Dropdown, FormControl, ScrollArea, Spinner, debounce, toast } from 'frappe-ui'
import ConversationRow from './ConversationRow.vue'
import EmptyState from '@/components/Common/EmptyState.vue'
import ListSkeleton from '@/components/Common/ListSkeleton.vue'
import ResolveDialog from './ResolveDialog.vue'
import {
  STATUSES,
  agents,
  bulkUpdate,
  counts,
  inbox,
  labelMeta,
  labels,
  loadConversations,
  loadMoreConversations,
  loadResolveRules,
  setFilters,
} from '@/data/inbox'
import { session } from '@/data/session'
import { errorMessage } from '@/utils/format'
import { linkMeta } from '@/data/integrations'
import { translate as __ } from '@/translation'

defineProps({
  active: { type: String, default: null },
  compact: { type: Boolean, default: false },
})

const query = ref(inbox.search)
const selecting = ref(false)
const busy = ref(false)
const picked = ref(new Set())

const allPicked = computed(() => inbox.rows.length > 0 && inbox.rows.every((row) => picked.value.has(row.name)))

function toggleSelecting() {
  selecting.value = !selecting.value
  picked.value = new Set()
}

function pick(name) {
  const next = new Set(picked.value)
  if (next.has(name)) next.delete(name)
  else next.add(name)
  picked.value = next
}

function pickAll() {
  picked.value = allPicked.value ? new Set() : new Set(inbox.rows.map((row) => row.name))
}

const rules = ref({ require_reason: false, reasons: [], when_waiting: 'Allow', only_owner: false, is_admin: false })
const resolving = ref(false)

async function resolvePicked() {
  try {
    rules.value = await loadResolveRules()
  } catch {
    rules.value = { ...rules.value }
  }
  if (rules.value.require_reason || rules.value.require_note || rules.value.when_waiting !== 'Allow') {
    resolving.value = true
    return
  }
  apply('status', 'Resolved')
}

async function apply(action, value = null, extra = {}) {
  const contacts = [...picked.value]
  if (!contacts.length) return
  busy.value = true
  try {
    const done = await bulkUpdate(contacts, action, value, extra)
    resolving.value = false
    if (done < contacts.length) {
      toast.warning(__('{0} of {1} conversations updated. The rest are blocked by your resolve rules.').format(done, contacts.length))
    } else {
      toast.success(__('{0} conversations updated').format(done))
    }
    selecting.value = false
    picked.value = new Set()
  } catch (error) {
    toast.error(errorMessage(error))
  } finally {
    busy.value = false
  }
}

const assignOptions = computed(() => [
  { label: __('Assign to me'), icon: 'lucide-user', onClick: () => apply('assign', session.user.name) },
  { label: __('Unassign'), icon: 'lucide-user-x', onClick: () => apply('assign', '') },
  {
    group: __('Teammates'),
    options: (agents.data || [])
      .filter((row) => row.name !== session.user.name)
      .map((row) => ({ label: row.full_name || row.name, onClick: () => apply('assign', row.name) })),
  },
])

const channels = computed(() => counts.data?.channels || [])


const labelOptions = computed(() => {
  const rows = labels.data || []
  if (!rows.length) return []
  return [
    {
      group: __('Add label'),
      options: rows.map((row) => ({ label: row.label_name || row.name, onClick: () => apply('add_label', row.name) })),
    },
    {
      group: __('Remove label'),
      options: rows.map((row) => ({ label: row.label_name || row.name, onClick: () => apply('remove_label', row.name) })),
    },
  ]
})

const statusOptions = computed(() =>
  Object.values(STATUSES).map((status) => ({
    label: __(status),
    onClick: () => (status === 'Resolved' ? resolvePicked() : apply('status', status)),
  })),
)
const scrollArea = ref(null)
const sentinel = ref(null)

const search = debounce(
  (value) => setFilters({ view: inbox.view, link: inbox.link, status: inbox.status, label: inbox.label, search: value.trim() }),
  300,
)

watch(query, (value) => search(value || ''))

const EMPTY = {
  all: {
    icon: 'lucide-message-circle',
    title: 'No conversations yet',
    description: 'When a customer messages your WhatsApp number, the chat shows up here.',
  },
  unread: {
    icon: 'lucide-mail-check',
    title: 'No unread conversations',
    description: 'You are all caught up.',
  },
  mine: {
    icon: 'lucide-user-check',
    title: 'Nothing assigned to you',
    description: 'Conversations assigned to you will appear here.',
  },
  mentions: {
    icon: 'lucide-at-sign',
    title: 'No mentions',
    description: 'When a teammate mentions you in an internal note, the conversation shows up here for 30 days.',
  },
  overdue: {
    icon: 'lucide-timer',
    title: 'Nothing overdue',
    description: 'Chats waiting longer than your reply time show up here.',
  },
  followups: {
    icon: 'lucide-bell-ring',
    title: 'No follow-ups',
    description: 'Set a reminder from a chat and it waits here until it is due.',
  },
  snoozed: {
    icon: 'lucide-alarm-clock',
    title: 'Nothing snoozed',
    description: 'Snoozed chats wait here and come back at the time you pick, or when the customer replies.',
  },
}

const EMPTY_STATUS = {
  open: {
    icon: 'lucide-circle-dot',
    title: 'No open conversations',
    description: 'New and reopened conversations show up here.',
  },
  pending: {
    icon: 'lucide-clock',
    title: 'No pending conversations',
    description: 'Conversations you mark as pending wait here.',
  },
  resolved: {
    icon: 'lucide-circle-check',
    title: 'No resolved conversations',
    description: 'Conversations you resolve are kept here.',
  },
}

const empty = computed(() => {
  if (inbox.search) {
    return {
      icon: 'lucide-search-x',
      title: __('No matches'),
      description: __('No conversation matches "{0}".').format(inbox.search),
    }
  }

  const base = EMPTY_STATUS[inbox.status] || EMPTY[inbox.view] || EMPTY.all
  if (inbox.label) {
    return {
      icon: 'lucide-tag',
      title: __('No conversations labelled {0}').format(labelMeta(inbox.label).label_name),
      description: __('Add this label to a conversation from its header.'),
    }
  }

  const link = inbox.link ? linkMeta(inbox.link) : null
  const title = link ? __('No conversations with {0}').format(link.label.toLowerCase()) : __(base.title)

  return { icon: link?.icon || base.icon, title, description: __(base.description) }
})

let observer = null

watch(
  [sentinel, () => inbox.rows.length],
  ([element]) => {
    observer?.disconnect()
    if (!element) return

    observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) loadMoreConversations()
      },
      { root: scrollArea.value?.viewportElement || null, rootMargin: '200px' },
    )
    observer.observe(element)
  },
  { flush: 'post' },
)

onMounted(() => {
  if (!agents.data) agents.fetch()
})

onBeforeUnmount(() => observer?.disconnect())
</script>
