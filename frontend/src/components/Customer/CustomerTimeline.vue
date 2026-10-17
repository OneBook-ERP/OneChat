<template>
  <div class="flex flex-col gap-3">
    <div v-if="filterable" class="flex flex-wrap gap-1.5">
      <Button
        v-for="option in filters"
        :key="option.value"
        size="sm"
        :variant="kind === option.value ? 'solid' : 'subtle'"
        :label="option.label"
        @click="setKind(option.value)"
      />
    </div>

    <div v-if="loading && !events.length" class="flex flex-col gap-3">
      <div v-for="index in compact ? 3 : 6" :key="index" class="flex items-start gap-3">
        <Skeleton class="size-8 shrink-0 rounded-full" />
        <div class="flex flex-1 flex-col gap-1.5">
          <Skeleton class="h-4 w-2/3 rounded-full" />
          <Skeleton class="h-3 w-1/3 rounded-full" />
        </div>
      </div>
    </div>

    <ErrorMessage v-else-if="error" :message="error" />

    <EmptyState
      v-else-if="!events.length"
      :compact="compact"
      :icon="kind === 'all' ? 'lucide-history' : kindMeta(kind).icon"
      :title="
        kind === 'all' ? __('Nothing has happened with this customer yet') : __('No {0} yet').format(__(kindMeta(kind).label).toLowerCase())
      "
      :description="compact ? '' : __(EMPTY_HINTS[kind] || EMPTY_HINTS.all)"
    />

    <template v-else>
      <section v-for="group in groups" :key="group.day" class="flex flex-col">
        <p v-if="!compact" class="sticky top-0 z-[1] bg-surface-base py-1.5 text-xs font-medium uppercase tracking-wide text-ink-gray-5">
          {{ group.label }}
        </p>
        <ol class="flex flex-col">
          <li v-for="(item, index) in group.events" :key="item.id" class="relative flex gap-3 pb-4 last:pb-2">
            <span
              v-if="index < group.events.length - 1"
              class="absolute bottom-0 left-4 top-9 w-px -translate-x-1/2 bg-outline-gray-2"
              aria-hidden="true"
            />
            <span class="relative flex size-8 shrink-0 items-center justify-center rounded-full" :class="kindMeta(item.kind).tile">
              <span :class="item.icon || kindMeta(item.kind).icon" class="size-4" aria-hidden="true" />
            </span>
            <component
              :is="linkOf(item) ? 'button' : 'div'"
              :type="linkOf(item) ? 'button' : undefined"
              class="min-w-0 flex-1 rounded-4 text-left"
              :class="linkOf(item) ? '-mx-1.5 -my-1 px-1.5 py-1 transition-colors hover:bg-surface-gray-1' : ''"
              @click="linkOf(item) && open(item)"
            >
              <div class="flex items-start gap-2">
                <p class="min-w-0 flex-1 text-sm font-medium text-ink-gray-9">{{ item.title }}</p>
                <span class="shrink-0 text-xs tabular-nums text-ink-gray-5">{{ compact ? timeAgo(item.at) : clock(item.at) }}</span>
              </div>
              <TruncatedText as="p" v-if="item.subtitle" class="mt-0.5 truncate text-sm text-ink-gray-6" :text="item.subtitle" />
              <TruncatedText
                as="p"
                v-if="item.text"
                class="mt-1 line-clamp-3 whitespace-pre-wrap break-words text-sm text-ink-gray-7"
                :text="item.text"
              />
              <Badge v-if="item.status" class="mt-1.5" size="sm" :theme="item.theme || 'gray'" :label="item.status" />
            </component>
          </li>
        </ol>
      </section>

      <Button
        v-if="cursor && !compact"
        class="self-center"
        variant="subtle"
        :loading="loading"
        :label="__('Load older')"
        @click="load(true)"
      />
    </template>
  </div>
</template>

<script setup>
import EmptyState from '@/components/Common/EmptyState.vue'
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Badge, Button, ErrorMessage, Skeleton } from 'frappe-ui'
import { TIMELINE_KINDS, customerTimeline, kindMeta } from '@/data/customer'

const EMPTY_HINTS = {
  all: 'Chats, notes, orders, campaigns and consent changes show up here as they happen.',
  conversation: 'Conversations with this customer are listed here.',
  record: 'Orders, invoices and payments from linked records appear here.',
  note: 'Notes your team adds about this customer appear here.',
  campaign: 'Broadcasts and notifications sent to this customer appear here.',
  form: 'Forms this customer submits appear here.',
  flow: 'Chatbot runs for this customer appear here.',
  link: 'When this customer arrives through a chat link, it shows here.',
  consent: 'Marketing opt-ins and opt-outs appear here.',
}
import { hasRecords } from '@/data/integrations'
import { clock, dayLabel, errorMessage, timeAgo } from '@/utils/format'
import { translate as __ } from '@/translation'

const props = defineProps({
  contact: { type: String, required: true },
  compact: { type: Boolean, default: false },
  filterable: { type: Boolean, default: false },
  limit: { type: Number, default: 30 },
})

const router = useRouter()

const events = ref([])
const cursor = ref(null)
const loading = ref(false)
const error = ref('')
const kind = ref('all')
let ticket = 0

const filters = computed(() => [
  { value: 'all', label: __('All') },
  ...TIMELINE_KINDS.filter((row) => row.value !== 'record' || hasRecords.value).map((row) => ({ value: row.value, label: __(row.label) })),
])

const groups = computed(() => {
  const out = []
  for (const item of events.value) {
    const day = String(item.at).slice(0, 10)
    let group = out[out.length - 1]
    if (!group || group.day !== day) {
      group = { day, label: dayLabel(item.at), events: [] }
      out.push(group)
    }
    group.events.push(item)
  }
  return out
})

function linkOf(item) {
  return item.route || item.url
}

function open(item) {
  if (item.route) router.push(item.route)
  else if (item.url) window.open(item.url, '_blank', 'noopener')
}

async function load(more = false) {
  const current = ++ticket
  loading.value = true
  error.value = ''
  try {
    const result = await customerTimeline(props.contact, {
      before: more ? cursor.value : null,
      kinds: kind.value === 'all' ? null : [kind.value],
      limit: props.limit,
    })
    if (current !== ticket) return
    const known = new Set(more ? events.value.map((item) => item.id) : [])
    events.value = [...(more ? events.value : []), ...result.events.filter((item) => !known.has(item.id))]
    cursor.value = result.cursor
  } catch (err) {
    if (current === ticket) error.value = errorMessage(err)
  } finally {
    if (current === ticket) loading.value = false
  }
}

function setKind(value) {
  kind.value = value
  load()
}

watch(
  () => props.contact,
  () => {
    kind.value = 'all'
    events.value = []
    load()
  },
  { immediate: true },
)

defineExpose({ reload: () => load() })
</script>
