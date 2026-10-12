<template>
  <div class="flex flex-col gap-1">
    <FormControl
      v-if="(labels.data || []).length > 8"
      v-model="query"
      type="search"
      :size="large ? 'lg' : 'sm'"
      class="mb-1"
      :placeholder="__('Find a label')"
    >
      <template v-if="large" #prefix>
        <span class="lucide-search size-4 text-ink-gray-5" aria-hidden="true" />
      </template>
    </FormControl>

    <ScrollArea :viewport-class="large ? 'max-h-[50dvh]' : 'max-h-64'">
      <div v-if="filtered.length" role="listbox" :aria-label="__('Labels')" aria-multiselectable="true">
        <button
          v-for="row in filtered"
          :key="row.name"
          type="button"
          role="option"
          :aria-selected="selected.includes(row.name)"
          class="flex w-full items-center rounded-3 text-left text-ink-gray-8 focus-visible:focus-ring"
          :class="large ? 'h-11 gap-3 px-2 text-base active:bg-surface-gray-2' : 'gap-2 px-2 py-1.5 text-sm hover:bg-surface-gray-2'"
          @click="toggle(row.name)"
        >
          <span
            class="shrink-0 rounded-full"
            :class="[LABEL_DOTS[row.color] || LABEL_DOTS.gray, large ? 'size-2.5' : 'size-2']"
            aria-hidden="true"
          />
          <TruncatedText class="min-w-0 flex-1 truncate" :text="row.label_name || row.name" />
          <span v-if="selected.includes(row.name)" class="lucide-check size-4 shrink-0 text-ink-gray-7" aria-hidden="true" />
        </button>
      </div>
      <p v-else-if="labels.loading && !(labels.data || []).length" class="px-2 py-3 text-sm text-ink-gray-5">
        {{ __('Loading…') }}
      </p>
      <p v-else-if="query" class="px-2 py-3 text-sm text-ink-gray-5">{{ __('No label matches that search') }}</p>
      <p v-else class="px-2 py-3 text-sm text-ink-gray-5">
        {{
          session.user.is_admin
            ? __('No labels yet. Create them under Settings → Labels.')
            : __('No labels yet. Ask an admin to create some.')
        }}
      </p>
    </ScrollArea>
  </div>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { computed, onMounted, ref } from 'vue'
import { FormControl, ScrollArea, toast } from 'frappe-ui'
import { LABEL_DOTS, labels, setLabels } from '@/data/inbox'
import { session } from '@/data/session'
import { errorMessage } from '@/utils/format'
import { translate as __ } from '@/translation'

const props = defineProps({
  contact: { type: String, required: true },
  modelValue: { type: Array, default: () => [] },
  large: { type: Boolean, default: false },
})

const query = ref('')

const selected = computed(() => props.modelValue || [])

const filtered = computed(() => {
  const text = query.value.trim().toLowerCase()
  const rows = labels.data || []
  if (!text) return rows

  return rows.filter((row) => `${row.label_name || row.name}`.toLowerCase().includes(text))
})

async function toggle(name) {
  const next = selected.value.includes(name) ? selected.value.filter((value) => value !== name) : [...selected.value, name]

  try {
    await setLabels(props.contact, next)
  } catch (error) {
    toast.error(errorMessage(error))
  }
}

onMounted(() => labels.reload())
</script>
