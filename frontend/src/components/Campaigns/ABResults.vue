<template>
  <section v-if="data" class="flex flex-col gap-3 rounded-5 border border-outline-gray-1 p-3">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <div class="min-w-0">
        <p class="text-base font-medium text-ink-gray-8">{{ __('A/B test') }}</p>
        <p class="text-sm text-ink-gray-5">{{ statusLine }}</p>
      </div>
      <div v-if="data.status === 'Testing'" class="flex gap-2">
        <Button
          v-for="variant in ['A', 'B']"
          :key="variant"
          size="sm"
          :variant="variant === data.leader ? 'solid' : 'subtle'"
          :loading="sending === variant"
          :label="__('Send {0} now').format(variant)"
          @click="send(variant)"
        />
      </div>
    </div>

    <div class="grid gap-2 sm:grid-cols-2">
      <div
        v-for="variant in ['A', 'B']"
        :key="variant"
        class="flex flex-col gap-2 rounded-4 border p-3"
        :class="highlight === variant ? 'border-outline-green-2 bg-surface-green-1' : 'border-outline-gray-1'"
      >
        <div class="flex items-center gap-2">
          <span class="flex size-6 items-center justify-center rounded-full bg-surface-gray-2 text-sm font-semibold text-ink-gray-8">{{
            variant
          }}</span>
          <TruncatedText class="min-w-0 flex-1 truncate text-sm text-ink-gray-8" :text="data.templates[variant]" />
          <Badge v-if="data.winner === variant" theme="green" :label="__('Winner')" />
          <Badge v-else-if="data.status === 'Testing' && data.leader === variant" theme="blue" variant="outline" :label="__('Leading')" />
        </div>
        <dl class="grid grid-cols-3 gap-2 text-center">
          <div>
            <dt class="text-xs text-ink-gray-5">{{ __('Sent') }}</dt>
            <dd class="text-base font-semibold tabular-nums text-ink-gray-9">{{ formatNumber(data.variants[variant].sent) }}</dd>
          </div>
          <div>
            <dt class="text-xs text-ink-gray-5">{{ __('Read') }}</dt>
            <dd class="text-base font-semibold tabular-nums text-ink-gray-9">{{ data.variants[variant].read_rate }}%</dd>
          </div>
          <div>
            <dt class="text-xs text-ink-gray-5">{{ __('Replied') }}</dt>
            <dd class="text-base font-semibold tabular-nums text-ink-gray-9">{{ data.variants[variant].reply_rate }}%</dd>
          </div>
        </dl>
      </div>
    </div>
  </section>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Badge, Button, call, toast } from 'frappe-ui'
import { useUI } from '@/stores/ui'
import { errorMessage, formatDateTime, formatNumber } from '@/utils/format'
import { translate as __ } from '@/translation'

const props = defineProps({ name: { type: String, required: true } })
const emit = defineEmits(['changed'])

const ui = useUI()
const data = ref(null)
const sending = ref(null)
let timer = null

const highlight = computed(() => data.value?.winner || (data.value?.status === 'Testing' ? data.value.leader : null))
const statusLine = computed(() => {
  const row = data.value
  if (!row) return ''
  const metric = row.metric === 'Reads' ? __('reads') : __('replies')
  if (row.status === 'Testing') {
    return __('Picking the version with more {0} at {1}. {2} recipients are waiting.').format(
      metric,
      formatDateTime(row.decide_at),
      formatNumber(row.waiting),
    )
  }
  return row.winner ? __('Version {0} won on {1} and was sent to everyone else.').format(row.winner, metric) : ''
})

async function load() {
  try {
    data.value = await call('onechat.campaigns.ab_test.results', { name: props.name })
  } catch {
    data.value = null
  }
}

function send(variant) {
  ui.confirm({
    title: __('Send version {0} to everyone else?').format(variant),
    message: __('{0} waiting recipients get template {1} now, and the test ends.').format(
      formatNumber(data.value.waiting),
      data.value.templates[variant],
    ),
    action: __('Send {0}').format(variant),
    onConfirm: async () => {
      sending.value = variant
      try {
        data.value = await call('onechat.campaigns.ab_test.send_winner', { name: props.name, winner: variant })
        toast.success(__('Sending version {0} to everyone else').format(variant))
        emit('changed')
      } catch (err) {
        toast.error(errorMessage(err))
      } finally {
        sending.value = null
      }
    },
  })
}

watch(() => props.name, load)
onMounted(() => {
  load()
  timer = setInterval(() => {
    if (!document.hidden && data.value?.status === 'Testing') load()
  }, 30000)
})
onBeforeUnmount(() => clearInterval(timer))
</script>
