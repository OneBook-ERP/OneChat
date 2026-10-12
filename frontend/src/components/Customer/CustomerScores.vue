<template>
  <section class="flex flex-col gap-2 rounded-4 border border-outline-gray-1 px-3 py-2">
    <div class="flex items-center justify-between gap-2">
      <p class="text-sm font-medium text-ink-gray-8">{{ scores.purchases ? __('Customer scores') : __('Engagement') }}</p>
      <Tooltip :text="updatedHint">
        <Button variant="ghost" size="sm" icon="lucide-refresh-cw" :loading="refreshing" :label="__('Recalculate')" @click="refresh" />
      </Tooltip>
    </div>

    <div v-if="scores.purchases" class="flex flex-wrap items-center gap-2">
      <Tooltip :text="scores.group_hint || ''" :disabled="!scores.group_hint">
        <Badge size="lg" :theme="group.theme" :label="__(scores.value_group || 'Prospect')">
          <template #prefix>
            <span :class="group.icon" class="size-3.5" aria-hidden="true" />
          </template>
        </Badge>
      </Tooltip>
      <Badge v-if="scores.favourite_category" size="lg" variant="outline" :label="scores.favourite_category">
        <template #prefix>
          <span class="lucide-heart size-3.5" aria-hidden="true" />
        </template>
      </Badge>
    </div>

    <div class="flex flex-col gap-1.5">
      <div class="flex items-center justify-between text-sm">
        <Tooltip :text="__('From replies, conversations and read receipts in the last 90 days.')">
          <span class="cursor-default text-ink-gray-6 underline decoration-dotted underline-offset-2">{{ __('Score') }}</span>
        </Tooltip>
        <span class="tabular-nums text-ink-gray-8">
          <span class="font-semibold">{{ score }}</span>
          <span class="text-ink-gray-5">/100 · {{ __(engagement.label) }}</span>
        </span>
      </div>
      <Progress :value="score" size="sm" />
    </div>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Badge, Button, Progress, Tooltip, toast } from 'frappe-ui'
import { engagementTheme, groupMeta, refreshScores } from '@/data/segments'
import { errorMessage, timeAgo } from '@/utils/format'
import { translate as __ } from '@/translation'

const props = defineProps({
  contact: { type: String, required: true },
  scores: { type: Object, default: () => ({}) },
})
const emit = defineEmits(['updated'])

const refreshing = ref(false)

const group = computed(() => groupMeta(props.scores.value_group || 'Prospect'))
const score = computed(() => Number(props.scores.engagement_score) || 0)
const engagement = computed(() => engagementTheme(score.value))
const updatedHint = computed(() =>
  props.scores.scores_updated_at
    ? __('Updated {0}. Scores refresh every night.').format(timeAgo(props.scores.scores_updated_at))
    : __('Not calculated yet'),
)

async function refresh() {
  refreshing.value = true
  try {
    emit('updated', await refreshScores(props.contact))
  } catch (err) {
    toast.error(errorMessage(err))
  } finally {
    refreshing.value = false
  }
}
</script>
