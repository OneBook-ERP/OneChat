<template>
  <AppHeader>
    <template #actions>
      <Button
        v-if="session.user.is_admin"
        variant="subtle"
        icon-left="lucide-refresh-cw"
        :loading="recalculating"
        :label="__('Recalculate scores')"
        @click="recalculate"
      />
      <Button v-if="session.user.is_admin" variant="solid" icon-left="lucide-plus" :label="__('New segment')" @click="edit(null)" />
    </template>
  </AppHeader>

  <ScrollArea class="min-h-0 flex-1">
    <div class="mx-auto flex w-full max-w-[1100px] flex-col gap-6 px-3 pb-10 pt-5 sm:px-5">
      <ErrorMessage :message="error" />

      <section class="flex flex-col gap-3">
        <div class="flex items-baseline justify-between gap-3">
          <h2 class="text-lg font-semibold text-ink-gray-9">{{ __('Engagement') }}</h2>
          <p class="text-sm text-ink-gray-5">
            {{ overview.scored_at ? __('Scored {0}').format(timeAgo(overview.scored_at)) : __('Not scored yet. Use Recalculate scores.') }}
          </p>
        </div>
        <div class="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <template v-if="loading && !loaded">
            <Skeleton v-for="index in 4" :key="index" class="h-[4.5rem] w-full" />
          </template>
          <Tooltip
            v-for="band in ENGAGEMENT_BANDS"
            v-else
            :key="band.key"
            :text="__('{0}. Score {1}–{2}.').format(__(band.hint), band.min, band.max)"
          >
            <button
              type="button"
              class="flex min-w-0 items-center gap-3 rounded-4 border border-outline-gray-1 px-3 py-2.5 text-left transition-colors hover:bg-surface-gray-1"
              @click="openBand(band.key)"
            >
              <span class="flex size-8 shrink-0 items-center justify-center rounded-full" :class="TILES[band.theme]">
                <span :class="band.icon" class="size-4" aria-hidden="true" />
              </span>
              <span class="min-w-0 flex-1">
                <TruncatedText class="block truncate text-sm text-ink-gray-6" :text="__(band.label)" />
                <span class="block text-lg font-semibold tabular-nums text-ink-gray-9">{{
                  formatNumber(overview.engagement[band.key] || 0)
                }}</span>
              </span>
              <span class="shrink-0 text-xs tabular-nums text-ink-gray-5">{{ share(overview.engagement[band.key]) }}</span>
            </button>
          </Tooltip>
        </div>
      </section>

      <section v-if="overview.purchases" class="flex flex-col gap-3">
        <div class="flex items-baseline justify-between gap-3">
          <h2 class="text-lg font-semibold text-ink-gray-9">{{ __('Value groups') }}</h2>
        </div>
        <div class="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <template v-if="loading && !loaded">
            <Skeleton v-for="index in 8" :key="index" class="h-[4.5rem] w-full rounded-4" />
          </template>
          <Tooltip v-for="group in groups" v-else :key="group.value" :text="__(group.hint)">
            <button
              type="button"
              class="flex min-w-0 items-center gap-3 rounded-4 border border-outline-gray-1 px-3 py-2.5 text-left transition-colors hover:bg-surface-gray-1"
              @click="openGroup(group.value)"
            >
              <span class="flex size-8 shrink-0 items-center justify-center rounded-full" :class="TILES[group.theme]">
                <span :class="group.icon" class="size-4" aria-hidden="true" />
              </span>
              <span class="min-w-0">
                <TruncatedText class="block truncate text-sm text-ink-gray-6" :text="__(group.value)" />
                <span class="block text-lg font-semibold tabular-nums text-ink-gray-9">{{
                  formatNumber(overview.groups[group.value] || 0)
                }}</span>
              </span>
            </button>
          </Tooltip>
        </div>
      </section>

      <section class="flex flex-col gap-3">
        <h2 class="text-lg font-semibold text-ink-gray-9">{{ __('Segments') }}</h2>

        <div v-if="loading && !loaded" class="grid gap-3 md:grid-cols-2">
          <Skeleton v-for="index in 4" :key="index" class="h-32 w-full rounded-5" />
        </div>

        <EmptyState
          v-else-if="!segments.length"
          icon="lucide-users-round"
          :title="__('No segments yet')"
          :description="
            __(
              'Group contacts by what they buy, how they engage and how they are tagged. Segments update on their own and can be used as a broadcast audience.',
            )
          "
        >
          <Button v-if="session.user.is_admin" variant="solid" icon-left="lucide-plus" :label="__('New segment')" @click="edit(null)" />
        </EmptyState>

        <div v-else class="grid gap-3 md:grid-cols-2">
          <article v-for="row in segments" :key="row.name" class="flex min-w-0 flex-col gap-3 rounded-5 border border-outline-gray-1 p-4">
            <div class="flex items-start gap-3">
              <div class="min-w-0 flex-1">
                <TruncatedText as="p" class="truncate text-base font-semibold text-ink-gray-9" :text="row.segment_name" />
                <TruncatedText as="p" v-if="row.description" class="line-clamp-2 text-sm text-ink-gray-5" :text="row.description" />
              </div>
              <div class="shrink-0 text-right">
                <p class="text-xl font-semibold tabular-nums text-ink-gray-9">{{ formatNumber(row.member_count) }}</p>
                <p class="text-xs text-ink-gray-5">{{ __('contacts') }}</p>
              </div>
            </div>

            <div class="flex flex-wrap gap-1.5">
              <template v-for="(rule, index) in row.rules" :key="index">
                <span v-if="index" class="self-center text-xs uppercase text-ink-gray-4">{{
                  row.match === 'any' ? __('or') : __('and')
                }}</span>
                <Badge variant="outline" :label="describe(rule)" />
              </template>
            </div>

            <div class="mt-auto flex items-center justify-end gap-1.5">
              <Dropdown v-if="session.user.is_admin" :options="menu(row)" align="end">
                <Button variant="ghost" icon="lucide-ellipsis" :label="__('More actions')" />
              </Dropdown>
              <Button
                v-if="session.user.is_admin"
                variant="subtle"
                icon-left="lucide-send"
                :disabled="!row.member_count"
                :label="__('Broadcast')"
                @click="broadcast(row)"
              />
            </div>
          </article>
        </div>
      </section>
    </div>
  </ScrollArea>

  <SegmentEditor v-model:open="editorOpen" :segment="editing" @saved="load" />
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Badge, Button, Dropdown, ErrorMessage, ScrollArea, Skeleton, Tooltip, call, toast } from 'frappe-ui'
import AppHeader from '@/components/Layouts/AppHeader.vue'
import EmptyState from '@/components/Common/EmptyState.vue'
import SegmentEditor from '@/components/Segments/SegmentEditor.vue'
import {
  ENGAGEMENT_BANDS,
  NO_VALUE,
  OP_LABELS,
  VALUE_GROUPS,
  deleteSegment,
  refreshAllScores,
  segmentFields,
  segmentList,
} from '@/data/segments'
import { session } from '@/data/session'
import { useUI } from '@/stores/ui'
import { errorMessage, formatNumber, timeAgo } from '@/utils/format'
import { recall, remember } from '@/utils/swr'
import { translate as __ } from '@/translation'

defineProps({ compact: { type: Boolean, default: false } })

const TILES = {
  green: 'bg-surface-green-2 text-ink-green-7',
  blue: 'bg-surface-blue-2 text-ink-blue-7',
  amber: 'bg-surface-amber-2 text-ink-amber-7',
  red: 'bg-surface-red-2 text-ink-red-7',
  gray: 'bg-surface-gray-2 text-ink-gray-7',
}

const HINTS = {
  Champion: 'Buys often, bought recently and spends the most',
  Loyal: 'Buys regularly and bought in the last 3 months',
  'New customer': 'First purchase in the last 45 days',
  Promising: 'Bought recently but only once or twice',
  'Needs attention': 'Last purchase was 3 to 6 months ago',
  'At risk': 'Used to buy regularly, nothing in over 6 months',
  Lost: 'No purchase in over a year',
  Prospect: 'Has not bought anything yet',
}

const router = useRouter()
const ui = useUI()

const segments = ref([])
const fields = ref([])
const overview = reactive({ groups: {}, engagement: {}, scored_at: null, purchases: false })

const engagementTotal = computed(() => Object.values(overview.engagement || {}).reduce((sum, value) => sum + (value || 0), 0))

function share(value) {
  if (!engagementTotal.value) return ''
  return `${Math.round(((value || 0) * 100) / engagementTotal.value)}%`
}

function openBand(key) {
  router.push({ name: 'Contacts', query: { engagement: key } })
}
const loading = ref(false)
const loaded = ref(false)
const error = ref('')
const editorOpen = ref(false)
const editing = ref(null)
const recalculating = ref(false)

const groups = computed(() => VALUE_GROUPS.map((group) => ({ ...group, hint: HINTS[group.value] })))
const byKey = computed(() => Object.fromEntries(fields.value.map((row) => [row.key, row])))

function valueLabel(field, value) {
  const options = field?.options || []
  const label = (item) => options.find((row) => row.value === item)?.label || __(item)
  if (Array.isArray(value)) return field?.type === 'number' ? value.join(' – ') : value.map(label).join(', ')
  if (field?.type === 'date') return __('{0} days').format(value)
  return label(value)
}

function describe(rule) {
  const field = byKey.value[rule.field]
  const head = `${field?.label || rule.field} ${__(OP_LABELS[rule.op] || rule.op)}`
  return NO_VALUE.includes(rule.op) ? head : `${head} ${valueLabel(field, rule.value)}`
}

async function load() {
  loading.value = true
  error.value = ''
  const cached = recall('segments:overview')
  if (cached && !loaded.value) {
    segments.value = cached.list
    Object.assign(overview, cached.stats)
    loaded.value = true
  }
  try {
    const [list, stats, meta] = await Promise.all([
      segmentList(),
      call('onechat.inbox.segments.overview'),
      fields.value.length ? fields.value : segmentFields(),
    ])
    segments.value = list
    Object.assign(overview, stats)
    fields.value = meta
    loaded.value = true
    remember('segments:overview', { list, stats })
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    loading.value = false
  }
}

function edit(row) {
  editing.value = row
  editorOpen.value = true
}

function openGroup(value) {
  router.push({ name: 'Contacts', query: { group: value } })
}

function broadcast(row) {
  router.push({ name: 'Broadcasts', query: { segment: row.name } })
}

function menu(row) {
  return [
    { label: __('Edit'), icon: 'lucide-pencil', onClick: () => edit(row) },
    {
      label: __('Delete'),
      icon: 'lucide-trash-2',
      theme: 'red',
      onClick: () =>
        ui.confirm({
          title: __('Delete {0}?').format(row.segment_name),
          message: __('Contacts are not changed. Only the saved rules are removed.'),
          action: __('Delete'),
          theme: 'red',
          onConfirm: async () => {
            await deleteSegment(row.name)
            toast.success(__('Segment deleted'))
            load()
          },
        }),
    },
  ]
}

async function recalculate() {
  recalculating.value = true
  try {
    await refreshAllScores()
    toast.success(__('Recalculating scores in the background. This can take a few minutes.'))
  } catch (err) {
    toast.error(errorMessage(err))
  } finally {
    recalculating.value = false
  }
}

onMounted(load)
</script>
