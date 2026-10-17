<template>
  <ResponsiveDialog v-model:open="open" :title="__('Run details')" size="3xl">
    <template #default>
      <div v-if="loading" class="flex flex-col gap-3 py-2">
        <Skeleton v-for="row in 5" :key="row" class="h-9 w-full" />
      </div>

      <ErrorMessage v-else-if="error" :message="error" />

      <div v-else-if="log" class="flex flex-col gap-5">
        <div class="grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-4">
          <div class="col-span-2 min-w-0 sm:col-span-1">
            <p class="text-xs text-ink-gray-5">{{ __('Flow') }}</p>
            <TruncatedText as="p" class="truncate text-base font-medium text-ink-gray-8" :text="log.flow" />
          </div>
          <div>
            <p class="text-xs text-ink-gray-5">{{ __('Status') }}</p>
            <RunStatusBadge class="mt-0.5" :status="log.status" />
          </div>
          <div>
            <p class="text-xs text-ink-gray-5">{{ __('Started') }}</p>
            <p class="text-base text-ink-gray-8">{{ formatDateTime(log.start_time) }}</p>
          </div>
          <div>
            <p class="text-xs text-ink-gray-5">{{ __('Duration') }}</p>
            <p class="text-base text-ink-gray-8">{{ formatDuration(log.duration) || '—' }}</p>
          </div>
        </div>

        <div v-if="log.error_message" class="rounded-4 bg-surface-red-1 p-3">
          <p class="mb-1 text-sm font-medium text-ink-red-7">{{ __('Error') }}</p>
          <ScrollArea viewport-class="max-h-48">
            <pre v-if="failure.technical" class="whitespace-pre-wrap break-words font-mono text-xs leading-5 text-ink-red-7">{{
              log.error_message
            }}</pre>
            <template v-else>
              <p class="whitespace-pre-wrap break-words text-base text-ink-gray-9">{{ failure.message }}</p>
              <p v-if="failure.hint" class="mt-1.5 flex gap-1.5 text-sm text-ink-gray-7">
                <span class="lucide-lightbulb mt-0.5 size-3.5 shrink-0 text-ink-amber-6" aria-hidden="true" />
                {{ failure.hint }}
              </p>
            </template>
          </ScrollArea>
        </div>

        <div>
          <p class="mb-3 text-sm font-medium text-ink-gray-5">{{ __('Steps') }}</p>
          <p v-if="!steps.length" class="text-base text-ink-gray-5">{{ __('No steps were recorded.') }}</p>
          <ol v-else class="flex flex-col">
            <li v-for="(item, index) in steps" :key="index" class="relative flex gap-3 pb-4 last:pb-0">
              <span
                v-if="index < steps.length - 1"
                class="absolute left-[13px] top-7 h-[calc(100%-1.5rem)] w-px bg-surface-gray-4"
                aria-hidden="true"
              />
              <span class="relative flex size-7 shrink-0 items-center justify-center rounded-full" :class="colorOf(item.node_type).chip">
                <span :class="nodeDef(item.node_type).icon" class="size-3.5" aria-hidden="true" />
              </span>
              <div class="min-w-0 flex-1 pt-0.5">
                <div class="flex flex-wrap items-center gap-2">
                  <p class="text-base font-medium text-ink-gray-8">{{ item.label }}</p>
                  <RunStatusBadge :status="item.status" />
                  <span v-if="item.duration" class="text-sm text-ink-gray-5">{{ item.duration }}</span>
                </div>
                <p class="mt-0.5 truncate font-mono text-xs text-ink-gray-5">{{ item.node_type }} · {{ item.node_id }}</p>

                <details v-if="item.error" class="mt-2" open>
                  <summary class="cursor-pointer text-sm text-ink-red-7">{{ __('Error') }}</summary>
                  <ScrollArea class="mt-1 rounded-4 bg-surface-red-1" viewport-class="max-h-60">
                    <pre class="whitespace-pre-wrap break-words p-2 font-mono text-xs leading-5 text-ink-red-7">{{ item.error }}</pre>
                  </ScrollArea>
                </details>
                <details v-if="item.output" class="mt-2">
                  <summary class="cursor-pointer text-sm text-ink-gray-6">{{ __('Output') }}</summary>
                  <ScrollArea orientation="both" class="mt-1 rounded-4 bg-surface-gray-2" viewport-class="max-h-60">
                    <pre class="p-2 font-mono text-xs leading-5 text-ink-gray-7">{{ pretty(item.output) }}</pre>
                  </ScrollArea>
                </details>
              </div>
            </li>
          </ol>
        </div>

        <details v-if="log.trigger_data" class="rounded-4 border border-outline-gray-2 px-3 py-2">
          <summary class="cursor-pointer text-sm font-medium text-ink-gray-7">{{ __('Trigger data') }}</summary>
          <ScrollArea orientation="both" class="mt-2" viewport-class="max-h-72">
            <pre class="font-mono text-xs leading-5 text-ink-gray-7">{{ pretty(log.trigger_data) }}</pre>
          </ScrollArea>
        </details>

        <details v-if="log.context_json" class="rounded-4 border border-outline-gray-2 px-3 py-2">
          <summary class="cursor-pointer text-sm font-medium text-ink-gray-7">{{ __('Final context') }}</summary>
          <ScrollArea orientation="both" class="mt-2" viewport-class="max-h-72">
            <pre class="font-mono text-xs leading-5 text-ink-gray-7">{{ pretty(log.context_json) }}</pre>
          </ScrollArea>
        </details>

        <p class="font-mono text-xs text-ink-gray-4">{{ __('Run {0}').format(log.run_id) }} · {{ log.name }}</p>
      </div>
    </template>

    <template #actions>
      <div class="flex w-full justify-end gap-2">
        <Button v-if="log && showOpenFlow" variant="subtle" icon-left="lucide-git-fork" :label="__('Open flow')" @click="openFlow" />
        <Button variant="solid" :label="__('Done')" @click="open = false" />
      </div>
    </template>
  </ResponsiveDialog>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Button, ErrorMessage, ScrollArea, Skeleton, call, dayjs } from 'frappe-ui'
import ResponsiveDialog from '@/components/Common/ResponsiveDialog.vue'
import RunStatusBadge from './RunStatusBadge.vue'
import { formatDuration } from '@/components/FlowBuilder/api'
import { colorOf, nodeDef, readGraph } from '@/components/FlowBuilder/nodeTypes'
import { errorMessage, formatDateTime } from '@/utils/format'
import { translate as __ } from '@/translation'

const props = defineProps({
  name: { type: String, default: null },
  showOpenFlow: { type: Boolean, default: true },
})

const open = defineModel('open', { type: Boolean, default: false })

const router = useRouter()
const log = ref(null)
const labels = ref({})
const loading = ref(false)
const error = ref('')

watch(
  [open, () => props.name],
  async ([value, name]) => {
    if (!value || !name) return

    loading.value = true
    error.value = ''
    log.value = null
    labels.value = {}

    try {
      log.value = await call('onechat.automation.flows.get_execution_log', { log_name: name })
      loadLabels(log.value.flow)
    } catch (err) {
      error.value = errorMessage(err)
    } finally {
      loading.value = false
    }
  },
  { immediate: true },
)

async function loadLabels(flow) {
  try {
    const data = await call('frappe.client.get_value', {
      doctype: 'OneChat Flow',
      filters: flow,
      fieldname: 'graph_json',
    })
    labels.value = Object.fromEntries(readGraph(data?.graph_json).nodes.map((node) => [node.id, node.data.label]))
  } catch {
    labels.value = {}
  }
}

const failure = computed(() => {
  const text = String(log.value?.error_message || '')
  if (/Traceback \(most recent call last\)/.test(text)) return { technical: true }
  const [message, ...rest] = text.split(/\r?\n/)
  return { message, hint: rest.join(' ').trim() }
})

const steps = computed(() => {
  const out = []

  for (const step of log.value?.execution_steps || []) {
    const pending =
      step.status !== 'Started' && [...out].reverse().find((item) => item.node_id === step.node_id && item.status === 'Started')
    const target = pending || { node_id: step.node_id, node_type: step.node_type, start: step.timestamp }

    target.status = step.status
    target.end = step.timestamp
    if (step.output) target.output = step.output
    if (step.error) target.error = step.error
    if (step.duration) target.seconds = step.duration

    if (!pending) out.push(target)
  }

  return out.map((item) => {
    const seconds = item.seconds || (item.start && item.end ? dayjs(item.end).diff(dayjs(item.start)) / 1000 : 0)

    return {
      ...item,
      label: labels.value[item.node_id] || nodeDef(item.node_type).label,
      duration: formatDuration(seconds),
    }
  })
})

function pretty(value) {
  try {
    return JSON.stringify(JSON.parse(value), null, 2)
  } catch {
    return value
  }
}

function openFlow() {
  open.value = false
  router.push({ name: 'FlowBuilder', params: { name: log.value.flow } })
}
</script>
