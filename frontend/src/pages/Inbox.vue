<template>
  <AppHeader v-if="!threadOnly" :tail="tail">
    <template #actions>
      <Button
        variant="ghost"
        icon="lucide-refresh-cw"
        :tooltip="__('Refresh')"
        :label="__('Refresh')"
        :loading="inbox.loading && inbox.loaded"
        @click="refresh"
      />
    </template>
  </AppHeader>

  <div class="flex h-full min-h-0">
    <ConversationList
      v-if="compact ? !contactName : listOpen || !contactName"
      :active="contactName"
      :compact="compact"
      class="min-w-0"
      :class="compact ? 'flex-1' : 'w-72 shrink-0 border-r 2xl:w-80'"
    />

    <template v-if="contactName">
      <Thread
        :key="contactName"
        :contact-name="contactName"
        :compact="compact"
        :panel-open="!compact && panelOpen"
        :list-open="listOpen"
        :back="back"
        @details="toggleDetails"
        @list="setList(!listOpen)"
      />
      <ContactPanel
        v-if="!compact && panelOpen"
        :key="`panel-${contactName}`"
        :contact-name="contactName"
        class="w-72 shrink-0 border-l 2xl:w-80"
        @close="setPanel(false)"
      />
    </template>

    <div v-else-if="!compact" class="flex min-w-0 flex-1 flex-col items-center justify-center gap-3 p-6 text-center">
      <EmptyStateIllustration name="conversation" :size="140" />
      <div>
        <p class="text-base font-medium text-ink-gray-8">{{ __('Pick a conversation') }}</p>
        <p class="mt-1 max-w-xs text-sm text-ink-gray-5">
          {{ __('Choose a chat from the list to read and reply. Use Alt + ↑ / ↓ to move between conversations.') }}
        </p>
      </div>
    </div>
  </div>

  <BottomSheet v-if="threadOnly" v-model:open="sheetOpen" :title="__('Contact details')">
    <ContactPanel :contact-name="contactName" compact />
    <div class="h-[calc(1rem+env(safe-area-inset-bottom))]" />
  </BottomSheet>
</template>

<script setup>
import EmptyStateIllustration from '@/components/Common/EmptyStateIllustration.vue'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { BottomSheet, Button } from 'frappe-ui'
import AppHeader from '@/components/Layouts/AppHeader.vue'
import ContactPanel from '@/components/Inbox/ContactPanel.vue'
import ConversationList from '@/components/Inbox/ConversationList.vue'
import Thread from '@/components/Inbox/Thread.vue'
import { STATUSES, findRow, inbox, loadConversations, loadThread, setFilters, startInbox } from '@/data/inbox'
import { useUI } from '@/stores/ui'
import { translate as __ } from '@/translation'

const PANEL_KEY = 'onechat-inbox-panel'
const LIST_KEY = 'onechat-inbox-list'
const VIEWS = ['unread', 'mine', 'mentions', 'overdue', 'followups', 'snoozed']

const props = defineProps({
  compact: { type: Boolean, default: false },
})

const route = useRoute()
const router = useRouter()
const ui = useUI()

const panelOpen = ref(readPanel())
const listOpen = ref(readList())
const sheetOpen = ref(false)

const contactName = computed(() => route.params.contact || null)

const threadOnly = computed(() => props.compact && !!contactName.value)

const title = computed(() => {
  const contact = { ...findRow(contactName.value), ...inbox.details[contactName.value] }
  return contact.contact_name || contact.mobile_no || contactName.value || ''
})

const tail = computed(() => (!props.compact && contactName.value ? [{ label: title.value }] : []))

const back = computed(() => ({ name: 'Inbox', query: route.query }))

function readPanel() {
  let saved = null

  try {
    saved = localStorage.getItem(PANEL_KEY)
  } catch {
    saved = null
  }

  return saved === null ? window.innerWidth >= 1280 : saved === '1'
}

function setPanel(value) {
  panelOpen.value = value

  try {
    localStorage.setItem(PANEL_KEY, value ? '1' : '0')
  } catch {
    return
  }
}

function readList() {
  try {
    return localStorage.getItem(LIST_KEY) !== '0'
  } catch {
    return true
  }
}

function setList(value) {
  listOpen.value = value

  try {
    localStorage.setItem(LIST_KEY, value ? '1' : '0')
  } catch {
    return
  }
}

function toggleDetails() {
  if (props.compact) sheetOpen.value = true
  else setPanel(!panelOpen.value)
}

function refresh() {
  loadConversations()
  if (contactName.value) loadThread(contactName.value).catch(() => {})
}

function step(offset) {
  const rows = inbox.rows
  if (!rows.length) return

  const index = rows.findIndex((row) => row.name === contactName.value)
  const next = rows[index === -1 ? 0 : index + offset]
  if (next) router.replace({ name: 'Inbox', params: { contact: next.name }, query: route.query })
}

function onKeydown(event) {
  if (!event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return
  if (event.key !== 'ArrowUp' && event.key !== 'ArrowDown') return

  event.preventDefault()
  step(event.key === 'ArrowUp' ? -1 : 1)
}

watch(
  () => [route.query.view, route.query.link, route.query.status, route.query.label],
  ([view, link, status, label]) => {
    setFilters({
      view: VIEWS.includes(view) ? view : 'all',
      link: link || null,
      status: status in STATUSES ? status : null,
      label: label || null,
    })
  },
  { immediate: true },
)

watch(
  threadOnly,
  (value, previous) => {
    if (value) ui.fullScreen = true
    else if (previous) ui.fullScreen = false
  },
  { immediate: true },
)

watch(contactName, () => (sheetOpen.value = false))

watch(
  () => inbox.focus,
  (focus) => {
    if (focus && props.compact) sheetOpen.value = false
  },
)

onMounted(() => {
  startInbox()
  document.addEventListener('keydown', onKeydown)
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKeydown)
  if (props.compact && contactName.value) ui.fullScreen = false
})
</script>
