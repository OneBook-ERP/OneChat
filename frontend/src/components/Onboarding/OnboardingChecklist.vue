<template>
  <ResponsiveDialog v-model:open="onboarding.open" :title="__('Set up OneChat')" size="3xl">
    <template #default>
      <div class="flex flex-col gap-4">
        <div
          v-if="outcome"
          class="flex flex-wrap items-center gap-x-3 gap-y-2 rounded-4 px-3 py-2.5"
          :class="outcome.done ? 'bg-surface-green-1' : 'bg-surface-amber-1'"
          role="status"
        >
          <span
            :class="outcome.done ? 'lucide-circle-check text-ink-green-6' : 'lucide-triangle-alert text-ink-amber-6'"
            class="size-4 shrink-0"
            aria-hidden="true"
          />
          <p class="min-w-0 flex-1 text-sm text-ink-gray-8">
            <template v-if="outcome.done">
              <span class="font-medium">{{ __('{0} is done.').format(__(outcome.step.title)) }}</span>
              <template v-if="next"> {{ __('Next up: {0}.').format(__(next.title)) }}</template>
            </template>
            <template v-else>
              <span class="font-medium">{{ __('{0} isn’t finished yet.').format(__(outcome.step.title)) }}</span>
              {{ __(outcome.step.description) }}
            </template>
          </p>
          <div v-if="!outcome.done" class="flex shrink-0 gap-1.5">
            <Button size="sm" variant="subtle" :label="__('Check again')" :loading="checking" @click="checkAgain" />
            <Button size="sm" variant="solid" :label="__('Show me again')" @click="onboarding.start(outcome.step.key)" />
          </div>
        </div>

        <div class="flex items-center gap-3">
          <Progress class="flex-1" :value="percent" size="sm" />
          <span class="shrink-0 text-sm tabular-nums text-ink-gray-6">
            {{ __('{0} of {1} done').format(onboarding.doneCount, onboarding.steps.length) }}
          </span>
        </div>

        <div v-if="onboarding.loading && !onboarding.status" class="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
          <Skeleton v-for="row in 9" :key="row" class="h-14 w-full" />
        </div>

        <section v-for="group in onboarding.groups" v-else :key="group.key" class="flex flex-col gap-2">
          <p class="text-xs font-medium uppercase tracking-wide text-ink-gray-5">
            {{ __(group.label) }}
            <span class="tabular-nums text-ink-gray-4"
              >· {{ group.steps.filter((step) => step.done).length }}/{{ group.steps.length }}</span
            >
          </p>
          <div class="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
            <div
              v-for="step in group.steps"
              :key="step.key"
              class="group flex min-w-0 items-center gap-2.5 rounded-5 border px-2.5 py-2 transition-colors"
              :class="
                step.done
                  ? 'border-outline-gray-1 bg-surface-gray-1 hover:bg-surface-gray-2'
                  : next?.key === step.key
                  ? 'border-outline-gray-4 bg-surface-base shadow-sm hover:bg-surface-gray-1'
                  : 'border-outline-gray-2 bg-surface-base hover:bg-surface-gray-1'
              "
            >
              <Tooltip :text="toggleHint(step)">
                <button
                  type="button"
                  class="group/mark grid size-7 shrink-0 place-content-center rounded-full outline-none transition-colors focus-visible:ring-2 focus-visible:ring-outline-gray-4"
                  :class="
                    step.done
                      ? 'bg-surface-green-6 text-ink-white'
                      : 'bg-surface-gray-2 text-ink-gray-7 hover:bg-surface-green-2 hover:text-ink-green-7'
                  "
                  :aria-label="toggleHint(step)"
                  :disabled="marking === step.key || (step.done && !onboarding.marked.has(step.key))"
                  @click="toggle(step)"
                >
                  <span v-if="step.done" class="lucide-check size-3.5" aria-hidden="true" />
                  <template v-else>
                    <span :class="step.icon" class="size-3.5 group-hover/mark:hidden" aria-hidden="true" />
                    <span class="lucide-check hidden size-3.5 group-hover/mark:block" aria-hidden="true" />
                  </template>
                </button>
              </Tooltip>
              <button
                type="button"
                class="flex min-w-0 flex-1 items-center gap-2.5 text-left outline-none"
                :aria-label="step.done ? __('{0}, done. Show again').format(__(step.title)) : __('{0}. Show me').format(__(step.title))"
                @click="onboarding.start(step.key)"
              >
                <span class="min-w-0 flex-1">
                  <span class="flex items-center gap-1.5">
                    <TruncatedText
                      class="truncate text-sm font-medium"
                      :class="step.done ? 'text-ink-gray-5 line-through' : 'text-ink-gray-9'"
                      :text="__(step.title)"
                    />
                    <span v-if="step.optional && !step.done" class="shrink-0 text-[10px] uppercase text-ink-gray-4">{{
                      __('Optional')
                    }}</span>
                  </span>
                  <TruncatedText class="block truncate text-xs text-ink-gray-5" :text="__(step.description)" />
                </span>
                <span
                  class="lucide-arrow-right size-3.5 shrink-0 text-ink-gray-4 transition-transform group-hover:translate-x-0.5"
                  :class="{ 'opacity-0 group-hover:opacity-100': step.done }"
                  aria-hidden="true"
                />
              </button>
            </div>
          </div>
        </section>
      </div>
    </template>
    <template #actions>
      <div class="flex w-full items-center justify-between gap-2">
        <Button
          variant="ghost"
          :label="onboarding.dismissed ? __('Show in sidebar again') : __('Hide setup guide')"
          @click="onboarding.dismiss(!onboarding.dismissed)"
        />
        <Button
          v-if="next"
          variant="solid"
          icon-right="lucide-arrow-right"
          :label="__('Next: {0}').format(__(next.title))"
          @click="onboarding.start(next.key)"
        />
        <Button v-else variant="solid" :label="__('Close')" @click="onboarding.open = false" />
      </div>
    </template>
  </ResponsiveDialog>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { computed, ref } from 'vue'
import { Button, Progress, Skeleton, Tooltip, toast } from 'frappe-ui'
import ResponsiveDialog from '@/components/Common/ResponsiveDialog.vue'
import { useOnboarding } from '@/stores/onboarding'
import { errorMessage } from '@/utils/format'
import { translate as __ } from '@/translation'

const onboarding = useOnboarding()

const percent = computed(() => (onboarding.steps.length ? Math.round((onboarding.doneCount * 100) / onboarding.steps.length) : 0))
const marking = ref('')

function toggleHint(step) {
  if (!step.done) return __('Mark as done')
  return onboarding.marked.has(step.key) ? __('Marked as done. Click to undo') : __('Done. OneChat found this set up')
}

async function toggle(step) {
  if (step.done && !onboarding.marked.has(step.key)) return
  marking.value = step.key
  try {
    await onboarding.mark(step.key, !step.done)
  } catch (err) {
    toast.error(errorMessage(err))
  } finally {
    marking.value = ''
  }
}

const checking = ref(false)

const outcome = computed(() => {
  const value = onboarding.result
  const step = value && onboarding.steps.find((row) => row.key === value.key)
  return step ? { done: value.done, step } : null
})

async function checkAgain() {
  checking.value = true
  try {
    await onboarding.check(onboarding.result?.key)
  } catch (err) {
    toast.error(errorMessage(err))
  } finally {
    checking.value = false
  }
}

const next = computed(
  () => onboarding.steps.find((step) => !step.done && !step.optional) || onboarding.steps.find((step) => !step.done) || null,
)
</script>
