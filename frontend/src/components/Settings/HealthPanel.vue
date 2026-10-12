<template>
  <SettingsHeader>
    <div class="flex items-center justify-between gap-3">
      <div class="min-w-0">
        <h2 class="text-lg font-semibold text-ink-gray-8">{{ __('Health') }}</h2>
        <p class="mt-0.5 truncate text-sm text-ink-gray-6">{{ __('What OneChat depends on, checked live') }}</p>
      </div>
      <Button size="sm" icon-left="lucide-refresh-cw" :label="__('Check again')" :loading="loading" @click="load" />
    </div>
  </SettingsHeader>

  <SettingsBody>
    <ErrorMessage :message="error" class="pt-3" />

    <div v-if="loading && !checks.length" class="flex flex-col gap-2 pt-4">
      <Skeleton class="h-7 w-72" />
      <Skeleton v-for="item in 3" :key="item" class="h-28 w-full" />
    </div>

    <template v-else-if="checks.length">
      <div class="flex flex-wrap items-center gap-x-3 gap-y-2 pt-4">
        <TabButtons v-model="filter" :options="filters" />
        <div class="flex items-center gap-1.5">
          <Badge v-for="item in tally" :key="item.status" size="sm" variant="subtle" :theme="LOOK[item.status].theme" :label="item.label" />
        </div>
        <span class="ml-auto text-xs text-ink-gray-5">{{ __('Checked {0}').format(timeAgo(generatedAt)) }}</span>
      </div>

      <div v-if="!groups.length" class="mt-3 flex items-center gap-2 rounded-4 bg-surface-green-1 px-3 py-2.5 text-sm text-ink-green-8">
        <span class="lucide-circle-check size-4 shrink-0" aria-hidden="true" />
        {{ __('Everything is working.') }}
      </div>

      <div class="mt-3 flex flex-col gap-3">
        <section v-for="group in groups" :key="group.name" class="overflow-hidden rounded-4 border border-outline-gray-2">
          <header class="flex items-center justify-between gap-2 bg-surface-gray-1 px-3 py-1.5">
            <h3 class="text-sm font-medium text-ink-gray-7">{{ group.name }}</h3>
            <span class="flex items-center gap-1" :aria-label="group.summary">
              <span v-for="check in group.all" :key="check.key" class="size-1.5 rounded-full" :class="LOOK[check.status].dot" />
            </span>
          </header>
          <ul class="divide-y divide-outline-gray-1">
            <li
              v-for="check in group.checks"
              :key="check.key"
              class="grid grid-cols-[1rem_minmax(0,1fr)_auto] items-start gap-x-2.5 gap-y-0.5 px-3 py-2 sm:grid-cols-[1rem_11rem_minmax(0,1fr)_auto]"
            >
              <span
                :class="[LOOK[check.status].icon, 'mt-0.5 size-4', LOOK[check.status].ink]"
                :aria-label="__(LOOK[check.status].label)"
              />
              <TruncatedText class="truncate text-base font-medium leading-5 text-ink-gray-8" :text="check.title" />
              <div class="col-start-2 min-w-0 sm:col-start-3 sm:row-start-1">
                <p class="break-words text-sm leading-5 text-ink-gray-6">{{ check.detail }}</p>
                <p v-if="check.fix && check.status !== 'ok'" class="mt-0.5 flex items-start gap-1 text-sm leading-5 text-ink-gray-8">
                  <span class="lucide-corner-down-right mt-0.5 size-3.5 shrink-0 text-ink-gray-4" aria-hidden="true" />
                  {{ check.fix }}
                </p>
              </div>
              <Button
                v-if="check.link && check.status !== 'ok'"
                class="col-start-3 row-start-1 sm:col-start-4"
                size="sm"
                variant="ghost"
                icon-right="lucide-arrow-up-right"
                :label="__('Open')"
                @click="open(check.link)"
              />
            </li>
          </ul>
        </section>
      </div>
    </template>
  </SettingsBody>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Badge, Button, ErrorMessage, SettingsBody, SettingsHeader, Skeleton, TabButtons, call } from 'frappe-ui'
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { useSocket } from '@/data/socket'
import { useUI } from '@/stores/ui'
import { errorMessage, timeAgo } from '@/utils/format'
import { translate as __ } from '@/translation'

const PING_MS = 4000
const RANK = { error: 3, warn: 2, ok: 1, off: 0 }
const LOOK = {
  error: { icon: 'lucide-circle-x', ink: 'text-ink-red-6', dot: 'bg-surface-red-5', theme: 'red', label: 'Broken', count: '{0} broken' },
  warn: {
    icon: 'lucide-triangle-alert',
    ink: 'text-ink-amber-6',
    dot: 'bg-surface-amber-5',
    theme: 'amber',
    label: 'Needs attention',
    count: '{0} to check',
  },
  ok: {
    icon: 'lucide-circle-check',
    ink: 'text-ink-green-6',
    dot: 'bg-surface-green-5',
    theme: 'green',
    label: 'Working',
    count: '{0} working',
  },
  off: {
    icon: 'lucide-circle-minus',
    ink: 'text-ink-gray-4',
    dot: 'bg-surface-gray-4',
    theme: 'gray',
    label: 'Turned off',
    count: '{0} off',
  },
}

const ui = useUI()
const loading = ref(false)
const error = ref('')
const server = ref([])
const live = ref(null)
const generatedAt = ref(null)
let pingTimer = null
let loaded = false

const checks = computed(() => (live.value ? [...server.value.slice(0, 1), live.value, ...server.value.slice(1)] : server.value))

const filter = ref('problems')
const problems = computed(() => checks.value.filter((check) => RANK[check.status] >= RANK.warn))
const filters = computed(() => [
  { label: __('Problems ({0})').format(problems.value.length), value: 'problems' },
  { label: __('All ({0})').format(checks.value.length), value: 'all' },
])

const tally = computed(() =>
  Object.keys(LOOK)
    .map((status) => ({ status, total: checks.value.filter((check) => check.status === status).length }))
    .filter((item) => item.total)
    .map((item) => ({ ...item, label: __(LOOK[item.status].count).format(item.total) })),
)

const groups = computed(() => {
  const out = []
  for (const check of checks.value) {
    let group = out.find((row) => row.name === check.group)
    if (!group) out.push((group = { name: check.group, all: [], checks: [] }))
    group.all.push(check)
    if (filter.value === 'all' || RANK[check.status] >= RANK.warn) group.checks.push(check)
  }
  return out
    .filter((group) => group.checks.length)
    .map((group) => ({
      ...group,
      checks: [...group.checks].sort((a, b) => RANK[b.status] - RANK[a.status]),
      summary: tallyText(group.all),
    }))
})

function tallyText(rows) {
  return Object.keys(LOOK)
    .map((status) => [status, rows.filter((check) => check.status === status).length])
    .filter(([, total]) => total)
    .map(([status, total]) => __(LOOK[status].count).format(total))
    .join(', ')
}

function liveRow(status, detail, fix) {
  return { key: 'live', group: __('System'), title: __('Live updates'), status, detail, fix }
}

function pingSocket() {
  const socket = useSocket()
  clearTimeout(pingTimer)
  live.value = liveRow('warn', __('Checking…'))
  if (!socket.connected) {
    const retry = () => pingSocket()
    socket.once('connect', retry)
    pingTimer = setTimeout(() => {
      socket.off('connect', retry)
      live.value = liveRow(
        'error',
        __('This browser is not connected to the live update server.'),
        __('Check that the socket server is running (bench restart) and that your proxy forwards /socket.io.'),
      )
    }, PING_MS)
    return
  }
  const done = () => {
    clearTimeout(pingTimer)
    live.value = liveRow('ok', __('Connected, and OneChat’s handlers answered.'))
  }
  socket.once('onechat_pong', done)
  pingTimer = setTimeout(() => {
    socket.off('onechat_pong', done)
    live.value = liveRow(
      'error',
      __('Connected, but OneChat’s handlers did not answer. Typing indicators won’t show.'),
      __('Update the OneChat app so realtime/handlers.js is in the app folder, then bench restart.'),
    )
  }, PING_MS)
  socket.emit('onechat_ping')
}

async function load() {
  loading.value = true
  error.value = ''
  pingSocket()
  try {
    const result = await call('onechat.workspace.health.report')
    server.value = result.checks || []
    generatedAt.value = result.generated_at
    if (!loaded) filter.value = server.value.some((check) => RANK[check.status] >= RANK.warn) ? 'problems' : 'all'
    loaded = true
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    loading.value = false
  }
}

function open(link) {
  if (link.startsWith('settings:')) ui.settingsTab = link.slice('settings:'.length)
  else window.open(link, '_blank', 'noopener')
}

onMounted(load)
watch(problems, (rows) => !rows.length && loaded && (filter.value = 'all'))
onBeforeUnmount(() => clearTimeout(pingTimer))
</script>
