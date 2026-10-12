<template>
  <template v-if="allowed">
    <Transition
      enter-active-class="transition duration-200 ease-out motion-reduce:transition-none"
      enter-from-class="translate-y-3 opacity-0"
      leave-active-class="transition duration-150 ease-in motion-reduce:transition-none"
      leave-to-class="translate-y-3 opacity-0"
    >
      <aside
        v-if="assistantLauncher.open"
        class="fixed bottom-4 right-4 z-50 flex flex-col overflow-hidden rounded-6 border border-outline-gray-2 bg-surface-base shadow-2xl"
        :class="
          expanded ? 'h-[min(48rem,calc(100dvh-2rem))] w-[min(46rem,calc(100vw-2rem))]' : 'h-[min(38rem,calc(100dvh-5rem))] w-[26rem]'
        "
        role="dialog"
        :aria-label="__('Assistant')"
        @keydown.esc.stop="close"
      >
        <header class="flex shrink-0 items-center gap-2.5 border-b border-outline-gray-1 py-2 pl-3 pr-1.5">
          <AssistantIcon class="size-7 shrink-0 text-ink-green-6" />
          <div class="min-w-0 flex-1">
            <p class="text-base font-semibold leading-5 text-ink-gray-9">{{ __('Assistant') }}</p>
            <p class="truncate text-xs text-ink-gray-5">{{ assistantStatus.data?.provider }}</p>
          </div>
          <Button
            v-if="panel?.hasTurns"
            variant="ghost"
            icon="lucide-message-square-plus"
            :label="__('New chat')"
            :tooltip="__('New chat')"
            @click="panel.reset()"
          />
          <Button
            variant="ghost"
            :icon="expanded ? 'lucide-minimize-2' : 'lucide-maximize-2'"
            :label="expanded ? __('Make smaller') : __('Make larger')"
            :tooltip="expanded ? __('Make smaller') : __('Make larger')"
            @click="expanded = !expanded"
          />
          <Button variant="ghost" icon="lucide-x" :label="__('Close')" :tooltip="__('Close (Esc)')" @click="close" />
        </header>

        <div class="min-h-0 flex-1 p-3">
          <AssistantPanel
            ref="panel"
            bare
            fill
            :page="page"
            :page-label="pageLabel"
            :suggestions="prompts"
            :heading="__('What can I help you with?')"
            :subheading="__('I can look up and update customers, orders, invoices, stock, leads and chats for you.')"
            @inserted="close"
          />
        </div>
        <p class="shrink-0 px-3 pb-2 text-xs text-ink-gray-4">
          {{ __('Ctrl+J opens or closes the Assistant. Check important figures before you act on them.') }}
        </p>
      </aside>
    </Transition>

    <div
      v-if="!assistantLauncher.open"
      class="group fixed bottom-3 right-0 z-40 flex h-14 w-3 items-center justify-end overflow-hidden transition-[width] duration-200 focus-within:w-16 hover:w-16 motion-reduce:transition-none"
    >
      <span
        class="pointer-events-none absolute right-1 top-1/2 h-8 w-1 -translate-y-1/2 rounded-full bg-outline-gray-3 transition-opacity group-focus-within:opacity-0 group-hover:opacity-0"
        aria-hidden="true"
      />
      <Tooltip :text="__('Assistant (Ctrl+J)')">
        <button
          type="button"
          class="pointer-events-none mr-2 grid size-11 shrink-0 translate-x-4 place-content-center rounded-full border border-outline-gray-2 bg-surface-base text-ink-green-6 opacity-0 shadow-lg transition duration-200 hover:bg-surface-gray-1 focus-visible:pointer-events-auto focus-visible:translate-x-0 focus-visible:opacity-100 focus-visible:focus-ring group-hover:pointer-events-auto group-hover:translate-x-0 group-hover:opacity-100 motion-reduce:transition-none"
          :aria-label="__('Open the Assistant')"
          @click="assistantLauncher.open = true"
        >
          <AssistantIcon class="size-6" />
        </button>
      </Tooltip>
    </div>
  </template>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { Button, Tooltip } from 'frappe-ui'
import AssistantIcon from '@/components/Inbox/AssistantIcon.vue'
import AssistantPanel from '@/components/Inbox/AssistantPanel.vue'
import { assistantLauncher, assistantStatus, canChange } from '@/data/assistant'
import { inbox } from '@/data/inbox'
import { session } from '@/data/session'
import { translate as __ } from '@/translation'

const PROMPTS = {
  inbox: [
    { text: __('Which customers have unpaid invoices?'), icon: 'lucide-receipt-indian-rupee' },
    { text: __('List sales orders waiting for delivery'), icon: 'lucide-truck' },
    { text: __('Show leads created this week'), icon: 'lucide-sprout' },
    { text: __('Draft a follow-up for customers who went quiet'), icon: 'lucide-message-square-text' },
  ],
  contacts: [
    { text: __('Who are our top 5 customers this month?'), icon: 'lucide-trophy' },
    { text: __('Find customers with overdue invoices'), icon: 'lucide-clock-alert' },
    { text: __('Which leads have not been contacted yet?'), icon: 'lucide-sprout' },
    { text: __('Show customers who ordered last month but not this month'), icon: 'lucide-user-minus' },
  ],
  campaigns: [
    { text: __('Which items are low in stock?'), icon: 'lucide-package' },
    { text: __('What are our best-selling items this month?'), icon: 'lucide-trending-up' },
    { text: __('Draft a festive offer message for our customers'), icon: 'lucide-message-square-text' },
    { text: __('Which customers bought sofas this year?'), icon: 'lucide-users' },
  ],
  insights: [
    { text: __('Compare this month’s sales with last month'), icon: 'lucide-chart-column' },
    { text: __('Total outstanding amount across customers'), icon: 'lucide-receipt-indian-rupee' },
    { text: __('Top 5 items by revenue this quarter'), icon: 'lucide-trending-up' },
    { text: __('How many orders were delivered late?'), icon: 'lucide-truck' },
  ],
  general: [
    { text: __('What needs my attention today?'), icon: 'lucide-list-checks' },
    { text: __('Show unpaid invoices over ₹10,000'), icon: 'lucide-receipt-indian-rupee' },
    { text: __('List sales orders due this week'), icon: 'lucide-calendar' },
    { text: __('Summarise new leads from this week'), icon: 'lucide-sprout' },
  ],
}

const route = useRoute()
const panel = ref(null)
const expanded = ref(false)

const status = computed(() => assistantStatus.data || {})
const allowed = computed(
  () => session.user.name !== 'Guest' && !!status.value.ready && (session.user.is_system_manager || canChange(status.value.access)),
)

const contact = computed(() => (['Inbox', 'CustomerProfile'].includes(route.name) && route.params.contact) || '')
const contactName = computed(() => {
  if (!contact.value) return ''
  const row = inbox.rows.find((item) => item.name === contact.value)
  return row?.contact_name || row?.mobile_no || contact.value
})

const title = computed(() => __(route.meta?.title || String(route.name || 'OneChat')))
const page = computed(() => ({
  title: title.value,
  route: route.name,
  path: route.fullPath,
  params: Object.fromEntries(Object.entries(route.params || {}).filter(([, value]) => typeof value === 'string' && value)),
  contact: contact.value || undefined,
}))
const pageLabel = computed(() => (contactName.value ? `${title.value} · ${contactName.value}` : title.value))

const prompts = computed(() => {
  if (contact.value) return null
  return PROMPTS[route.meta?.section] || PROMPTS.general
})

function close() {
  assistantLauncher.open = false
}

function onKeydown(event) {
  if (!allowed.value || !(event.ctrlKey || event.metaKey) || event.altKey || event.shiftKey) return
  if (event.code !== 'KeyJ' && (event.key || '').toLowerCase() !== 'j') return
  event.preventDefault()
  assistantLauncher.open = !assistantLauncher.open
}

onMounted(() => window.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))
</script>
