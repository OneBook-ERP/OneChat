<template>
  <div class="flex min-h-0 flex-1 flex-col">
    <div class="flex shrink-0 items-center justify-between gap-2 px-3 pb-2 pt-3">
      <p v-if="!hideTitle" class="text-base font-semibold text-ink-gray-9">{{ __('Notifications') }}</p>
      <TabButtons :model-value="feed.tab" :options="tabs" @update:model-value="feed.setTab" />
      <Button
        variant="ghost"
        size="sm"
        icon-left="lucide-check-check"
        :disabled="!feed.unread"
        :label="__('Mark all as read')"
        @click="feed.markAll"
      />
    </div>

    <ScrollArea class="min-h-0 flex-1" :viewport-class="compact ? 'max-h-[32rem] px-1.5 pb-1.5' : 'px-1.5 pb-3'">
      <div v-if="feed.loading && !feed.items.length" class="flex flex-col gap-2 p-1.5">
        <div v-for="index in 4" :key="index" class="flex items-start gap-3">
          <Skeleton class="size-8 shrink-0 rounded-full" />
          <div class="flex flex-1 flex-col gap-1.5">
            <Skeleton class="h-4 w-4/5 rounded-full" />
            <Skeleton class="h-3 w-1/3 rounded-full" />
          </div>
        </div>
      </div>

      <div v-else-if="!feed.items.length" class="flex min-h-64 flex-col items-center justify-center gap-2 px-4 py-8 text-center">
        <EmptyStateIllustration name="notifications" :size="120" />
        <p class="text-base text-ink-gray-7">{{ feed.tab === 'unread' ? __('You are all caught up') : __('No notifications yet') }}</p>
      </div>

      <button
        v-for="item in feed.items"
        :key="item.name"
        type="button"
        class="flex w-full items-start gap-3 rounded-4 px-1.5 py-2 text-left transition-colors hover:bg-surface-gray-2"
        @click="open(item)"
      >
        <span class="flex size-8 shrink-0 items-center justify-center rounded-full" :class="kindOf(item).tile">
          <span :class="kindOf(item).icon" class="size-4" aria-hidden="true" />
        </span>
        <span class="min-w-0 flex-1">
          <TruncatedText
            class="line-clamp-2 text-sm"
            :class="item.read ? 'text-ink-gray-6' : 'font-medium text-ink-gray-9'"
            :text="item.subject"
          />
          <span class="mt-0.5 block text-xs text-ink-gray-5">{{ timeAgo(item.creation) }}</span>
        </span>
        <span v-if="!item.read" class="mt-2 size-2 shrink-0 rounded-full bg-surface-blue-5" :aria-label="__('Unread')" />
      </button>
    </ScrollArea>
  </div>
</template>

<script setup>
import EmptyStateIllustration from '@/components/Common/EmptyStateIllustration.vue'
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Button, ScrollArea, Skeleton, TabButtons } from 'frappe-ui'
import { useNotificationFeed } from '@/stores/notificationFeed'
import { useUI } from '@/stores/ui'
import { timeAgo } from '@/utils/format'
import { translate as __ } from '@/translation'

defineProps({
  compact: { type: Boolean, default: false },
  hideTitle: { type: Boolean, default: false },
})
const emit = defineEmits(['close'])

const feed = useNotificationFeed()
const router = useRouter()
const ui = useUI()

const tabs = [
  { label: __('Unread'), value: 'unread' },
  { label: __('All'), value: 'all' },
]

const KINDS = {
  mention: { icon: 'lucide-at-sign', tile: 'bg-surface-blue-2 text-ink-blue-7' },
  assigned: { icon: 'lucide-user-check', tile: 'bg-surface-green-2 text-ink-green-7' },
  overdue: { icon: 'lucide-timer', tile: 'bg-surface-red-2 text-ink-red-7' },
  reminder: { icon: 'lucide-bell-ring', tile: 'bg-surface-amber-2 text-ink-amber-7' },
  flow: { icon: 'lucide-workflow', tile: 'bg-surface-red-2 text-ink-red-7' },
  broadcast: { icon: 'lucide-megaphone', tile: 'bg-surface-violet-2 text-ink-violet-7' },
  budget: { icon: 'lucide-wallet', tile: 'bg-surface-amber-2 text-ink-amber-7' },
  webhook: { icon: 'lucide-webhook', tile: 'bg-surface-red-2 text-ink-red-7' },
  other: { icon: 'lucide-bell', tile: 'bg-surface-gray-2 text-ink-gray-7' },
}

function kindOf(item) {
  if (item.type === 'Mention') return KINDS.mention
  if (item.type === 'Assignment') return KINDS.assigned
  if (item.document_type === 'OneChat Contact') return /overdue/i.test(item.subject) ? KINDS.overdue : KINDS.reminder
  if (item.document_type === 'OneChat Flow') return KINDS.flow
  if (item.document_type === 'Bulk WhatsApp Message') return KINDS.broadcast
  if (item.document_type === 'OneChat Settings') return KINDS.budget
  if (item.document_type === 'Webhook') return KINDS.webhook
  return KINDS.other
}

function deskUrl(doctype, name) {
  return `/app/${doctype.toLowerCase().replace(/ /g, '-')}/${encodeURIComponent(name)}`
}

function open(item) {
  feed.markRead(item)
  emit('close')
  const { document_type: doctype, document_name: name } = item
  if (doctype === 'OneChat Contact' && name) return router.push({ name: 'Inbox', params: { contact: name } })
  if (doctype === 'OneChat Flow' && name) return router.push({ name: 'FlowBuilder', params: { name } })
  if (doctype === 'Bulk WhatsApp Message') return router.push({ name: 'Broadcasts' })
  if (doctype === 'OneChat Settings') return router.push({ name: 'Insights', query: { tab: 'costs' } })
  if (doctype === 'Webhook') return ui.openSettings('developers')
  if (doctype && name) window.open(deskUrl(doctype, name), '_blank', 'noopener')
}

onMounted(() => feed.load())
</script>
