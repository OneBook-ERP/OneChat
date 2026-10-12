<template>
  <AppHeader>
    <template #actions>
      <Button variant="subtle" icon-left="lucide-download" :label="__('Export')" :disabled="!rows.length" @click="openExport" />
    </template>
  </AppHeader>

  <div class="mx-auto flex min-h-0 w-full max-w-[1100px] flex-1 flex-col gap-3 px-3 pb-3 pt-5 sm:px-5">
    <div v-if="!isDesktop" class="flex shrink-0 items-center gap-2">
      <FormControl v-model="filters.contact" class="min-w-0 flex-1" size="lg" type="search" :placeholder="__('Search contact')">
        <template #prefix>
          <span class="lucide-search size-4 text-ink-gray-5" aria-hidden="true" />
        </template>
      </FormControl>

      <div class="relative shrink-0">
        <Button size="lg" variant="subtle" icon="lucide-sliders-horizontal" :label="__('Filters')" @click="sheet = true" />
        <Badge
          v-if="activeFilters"
          class="pointer-events-none absolute -right-1.5 -top-1.5 tabular-nums"
          variant="solid"
          theme="blue"
          size="sm"
          :label="String(activeFilters)"
        />
      </div>

      <Button
        v-if="activeFilters || filters.contact"
        class="shrink-0"
        size="lg"
        variant="ghost"
        icon="lucide-x"
        :label="__('Clear filters')"
        @click="clearFilters"
      />

      <ResponsiveDialog v-model:open="sheet" :title="__('Filters')" size="sm">
        <template #default>
          <FilterChips v-if="actionOptions.length > 2" v-model="filters.action" :label="__('Action')" :options="actionOptions" />
          <FilterChips v-model="filters.actor" :label="__('Who')" :options="peopleOptions" />
          <FilterChips v-model="filters.period" :label="__('Period')" :options="periods" />
        </template>
      </ResponsiveDialog>
    </div>

    <ScrollArea v-else orientation="horizontal" class="shrink-0" viewport-class="pb-1">
      <div class="flex w-max min-w-full items-center gap-2">
        <FormControl v-model="filters.contact" class="w-60 shrink-0" type="search" :placeholder="__('Search contact')">
          <template #prefix>
            <span class="lucide-search size-4 text-ink-gray-5" aria-hidden="true" />
          </template>
        </FormControl>
        <Select v-if="actionOptions.length > 2" v-model="filters.action" class="w-40 shrink-0" :options="actionOptions" />
        <Select v-model="filters.actor" class="w-40 shrink-0" :options="peopleOptions" />
        <Button
          v-if="activeFilters || filters.contact"
          class="shrink-0"
          variant="ghost"
          icon-left="lucide-x"
          :label="__('Clear')"
          @click="clearFilters"
        />
        <div class="flex flex-1 justify-end pl-2">
          <TabButtons v-model="filters.period" class="shrink-0" :options="periods" />
        </div>
      </div>
    </ScrollArea>

    <ErrorMessage :message="error" />

    <div v-if="loading && !rows.length" class="flex flex-col gap-4 pt-2">
      <div v-for="row in 8" :key="row" class="flex items-center gap-3">
        <Skeleton class="size-8 rounded-full" />
        <div class="flex-1 space-y-2">
          <Skeleton class="h-4 w-2/3 rounded-full" />
          <Skeleton class="h-3 w-1/3 rounded-full" />
        </div>
      </div>
    </div>

    <EmptyState
      v-else-if="!rows.length"
      icon="lucide-shield-check"
      :title="__('No activity')"
      :description="__('Nothing matches these filters. Try a longer period or clear the filters.')"
    >
      <Button v-if="activeFilters || filters.contact" variant="subtle" :label="__('Clear filters')" @click="clearFilters" />
    </EmptyState>

    <template v-else>
      <ScrollArea class="min-h-0 flex-1 rounded-5 border border-outline-gray-1" :class="{ 'opacity-60': loading }">
        <section v-for="day in days" :key="day.key">
          <p class="sticky top-0 z-[1] border-b border-outline-gray-1 bg-surface-base px-4 py-2 text-sm font-medium text-ink-gray-5">
            {{ day.label }}
          </p>
          <button
            v-for="row in day.rows"
            :key="row.key"
            type="button"
            class="flex w-full items-start gap-3 border-b border-outline-gray-1 px-4 py-3 text-left transition-colors last:border-b-0 hover:bg-surface-gray-1 active:bg-surface-gray-2"
            @click="open(row)"
          >
            <Avatar v-if="row.actor_kind === 'User'" :image="row.actor_image" :label="row.actor_name" size="md" class="mt-0.5 shrink-0" />
            <span v-else class="mt-0.5 grid size-7 shrink-0 place-content-center rounded-full bg-surface-gray-2">
              <span
                :class="row.actor_kind === 'Customer' ? 'lucide-user-round' : 'lucide-bot'"
                class="size-4 text-ink-gray-5"
                aria-hidden="true"
              />
            </span>

            <span class="min-w-0 flex-1">
              <span class="block text-base text-ink-gray-7">
                <template v-for="(part, index) in sentence(row)" :key="index">
                  <strong v-if="part.strong" class="font-medium text-ink-gray-9">{{ part.text }}</strong>
                  <template v-else>{{ part.text }}</template>
                </template>
              </span>
              <TruncatedText
                v-if="row.details && showDetails(row)"
                class="mt-0.5 block truncate text-sm text-ink-gray-5"
                :text="row.details"
              />
            </span>

            <span class="flex shrink-0 items-center gap-1.5 pt-0.5 text-sm text-ink-gray-5">
              <span :class="ICONS[row.action]" class="size-3.5" aria-hidden="true" />
              <Tooltip :text="formatDateTime(row.at)">
                <span class="tabular-nums">{{ clock(row.at) }}</span>
              </Tooltip>
            </span>
          </button>
        </section>
      </ScrollArea>

      <Pagination v-if="total > PAGE_SIZES[0]" v-model:page="page" :total="total" />
    </template>

    <ExportDialog
      v-model:open="exportOpen"
      :default-name="`onechat-audit-log-${dayjs().format('YYYY-MM-DD')}`"
      :filtered="narrowed"
      :filtered-count="total"
      :total-count="allCount"
      :limit="MAX_EXPORT"
      :build="buildExport"
    />
  </div>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Avatar,
  Badge,
  Button,
  ErrorMessage,
  FormControl,
  ScrollArea,
  Select,
  Skeleton,
  TabButtons,
  Tooltip,
  call,
  dayjs,
  debounce,
} from 'frappe-ui'
import AppHeader from '@/components/Layouts/AppHeader.vue'
import EmptyState from '@/components/Common/EmptyState.vue'
import ExportDialog from '@/components/Common/ExportDialog.vue'
import FilterChips from '@/components/Common/FilterChips.vue'
import Pagination from '@/components/Common/Pagination.vue'
import ResponsiveDialog from '@/components/Common/ResponsiveDialog.vue'
import { useBreakpoint } from '@/composables/useBreakpoint'
import { field, refField, useQueryState } from '@/composables/useQueryState'
import { clock, dayLabel, errorMessage, formatDateTime } from '@/utils/format'
import { PAGE_SIZES, pageLength } from '@/utils/paging'
import { translate as __ } from '@/translation'

const ICONS = {
  'Sent message': 'lucide-send',
  'Sent template': 'lucide-layout-template',
  Assigned: 'lucide-user-check',
  Resolved: 'lucide-circle-check',
  Reopened: 'lucide-rotate-ccw',
  'Marked pending': 'lucide-clock',
  'Opted out': 'lucide-bell-off',
  'Opted in': 'lucide-bell-ring',
  'Labels changed': 'lucide-tags',
  'Added note': 'lucide-notebook-pen',
}

const CATEGORIES = {
  messages: ['Sent message', 'Sent template'],
  assignments: ['Assigned'],
  status: ['Resolved', 'Reopened', 'Marked pending'],
  consent: ['Opted out', 'Opted in'],
  labels: ['Labels changed'],
  notes: ['Added note'],
}

const route = useRoute()
const router = useRouter()
const { isDesktop } = useBreakpoint()

const filters = reactive({ action: '', actor: '', contact: '', period: '30d' })
const page = ref(1)
const rows = ref([])
const total = ref(0)
const people = ref([])
const loading = ref(false)
const error = ref('')
const sheet = ref(false)
let token = 0

const periods = [
  { label: __('Today'), value: 'today' },
  { label: __('7 days'), value: '7d' },
  { label: __('30 days'), value: '30d' },
  { label: __('90 days'), value: '90d' },
  { label: __('All'), value: 'all' },
]

const category = computed(() => (CATEGORIES[route.query.category] ? route.query.category : ''))

const actionOptions = computed(() => [
  { label: __('All actions'), value: '' },
  ...(CATEGORIES[category.value] || Object.keys(ICONS)).map((action) => ({ label: __(action), value: action })),
])

const peopleOptions = computed(() => [{ label: __('Everyone'), value: '' }, ...people.value])

const activeFilters = computed(() => [filters.action, filters.actor, filters.period !== '30d'].filter(Boolean).length)

const days = computed(() => {
  const groups = []
  for (const row of rows.value) {
    const key = dayjs(row.at).format('YYYY-MM-DD')
    let group = groups[groups.length - 1]
    if (!group || group.key !== key) {
      group = { key, label: dayLabel(row.at), rows: [] }
      groups.push(group)
    }
    group.rows.push(row)
  }

  return groups
})

function sentence(row) {
  const actor = { text: row.actor_name, strong: true }
  const contact = { text: row.contact_name, strong: true }
  const text = (value) => ({ text: value })

  switch (row.action) {
    case 'Sent message':
      return [actor, text(` ${__('sent a message to')} `), contact]
    case 'Sent template':
      return [actor, text(` ${__('sent the template')} `), { text: row.details, strong: true }, text(` ${__('to')} `), contact]
    case 'Assigned':
      return row.details === __('Unassigned')
        ? [actor, text(` ${__('unassigned the conversation with')} `), contact]
        : [actor, text(` ${__('assigned the conversation with')} `), contact, text(` ${__('to')} `), { text: row.details, strong: true }]
    case 'Resolved':
      return [actor, text(` ${__('resolved the conversation with')} `), contact]
    case 'Reopened':
      return row.actor_kind === 'Customer'
        ? [contact, text(` ${__('messaged again and reopened the conversation')}`)]
        : [actor, text(` ${__('reopened the conversation with')} `), contact]
    case 'Marked pending':
      return [actor, text(` ${__('marked the conversation with')} `), contact, text(` ${__('as pending')}`)]
    case 'Opted out':
      return row.actor_kind === 'Customer'
        ? [contact, text(` ${__('opted out of marketing by replying STOP')}`)]
        : [actor, text(` ${__('opted')} `), contact, text(` ${__('out of marketing')}`)]
    case 'Opted in':
      return row.actor_kind === 'Customer'
        ? [contact, text(` ${__('opted back in by replying START')}`)]
        : [actor, text(` ${__('opted')} `), contact, text(` ${__('back in to marketing')}`)]
    case 'Labels changed':
      return [actor, text(` ${__('changed the labels on')} `), contact]
    case 'Added note':
      return [actor, text(` ${__('added a note on')} `), contact]
    default:
      return [actor, text(` ${__(row.action)} `), contact]
  }
}

function showDetails(row) {
  return !['Assigned', 'Sent template', 'Resolved', 'Reopened', 'Marked pending'].includes(row.action)
}

async function load() {
  const current = ++token
  loading.value = true
  error.value = ''
  try {
    const data = await call('onechat.workspace.audit.feed', {
      category: category.value || undefined,
      action: filters.action || undefined,
      actor: filters.actor || undefined,
      contact: filters.contact.trim() || undefined,
      period: filters.period,
      start: (page.value - 1) * pageLength.value,
      limit: pageLength.value,
    })
    if (current !== token) return
    rows.value = data.rows || []
    total.value = data.total || 0
  } catch (err) {
    if (current === token) error.value = errorMessage(err)
  } finally {
    if (current === token) loading.value = false
  }
}

const state = useQueryState(
  [
    field('action', filters, 'action', ''),
    field('actor', filters, 'actor', ''),
    field('q', filters, 'contact', ''),
    field('period', filters, 'period', '30d'),
    refField('page', page, 1),
  ],
  { size: true },
)

function reload() {
  if (state.restoring()) return load()
  page.value === 1 ? load() : (page.value = 1)
}

const reloadSoon = debounce(reload, 300)

function clearFilters() {
  Object.assign(filters, { action: '', actor: '', contact: '', period: '30d' })
}

function open(row) {
  if (row.contact) router.push({ name: 'Inbox', params: { contact: row.contact } })
}

const MAX_EXPORT = 2000
const exportOpen = ref(false)
const allCount = ref(null)

const narrowed = computed(() =>
  Boolean(filters.action || filters.actor || filters.contact.trim() || category.value || filters.period !== 'all'),
)

function feedParams(scope) {
  if (scope !== 'filtered') return { period: 'all' }
  return {
    category: category.value || undefined,
    action: filters.action || undefined,
    actor: filters.actor || undefined,
    contact: filters.contact.trim() || undefined,
    period: filters.period,
  }
}

async function openExport() {
  allCount.value = narrowed.value ? null : total.value
  exportOpen.value = true
  if (narrowed.value) {
    try {
      allCount.value = (await call('onechat.workspace.audit.feed', { period: 'all', limit: 1 })).total
    } catch {
      allCount.value = null
    }
  }
}

async function buildExport(scope) {
  const data = (await call('onechat.workspace.audit.export_feed', feedParams(scope))) || []
  const columns = [
    { key: 'at', label: __('When') },
    { key: 'actor_name', label: __('Who') },
    { key: 'action', label: __('Action') },
    { key: 'contact_name', label: __('Conversation') },
    { key: 'details', label: __('Details') },
  ]
  return { columns, rows: data.map((row) => ({ ...row, at: formatDateTime(row.at), action: __(row.action) })) }
}

watch(category, () => {
  if (!state.restoring()) filters.action = ''
  reload()
})
watch(() => [filters.action, filters.actor, filters.period], reload)
watch(() => filters.contact, reloadSoon)
watch(page, load)
watch(pageLength, reload)

onMounted(async () => {
  load()
  try {
    people.value = await call('onechat.workspace.audit.people')
  } catch {
    people.value = []
  }
})
</script>
