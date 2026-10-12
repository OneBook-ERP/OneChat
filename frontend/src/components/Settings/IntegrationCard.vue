<template>
  <article class="flex flex-col rounded-6 border border-outline-gray-2 bg-surface-base p-3.5 transition-shadow hover:shadow-md">
    <div class="flex items-start gap-3">
      <IntegrationLogo :logo="row.logo" :icon="row.icon" :label="row.label" size="sm" bare />
      <div class="min-w-0 flex-1">
        <button type="button" class="block max-w-full text-left" @click="emit('details')">
          <TruncatedText as="h3" class="truncate text-base font-semibold text-ink-gray-9 hover:underline" :text="row.label" />
        </button>
        <TruncatedText as="p" class="truncate text-sm text-ink-gray-5" :text="subtitle" />
      </div>
      <span class="inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium" :class="status.class">
        <span :class="status.icon" class="size-3" aria-hidden="true" />{{ status.label }}
      </span>
    </div>

    <TruncatedText
      as="p"
      class="mt-2 line-clamp-2 flex-1 text-sm leading-5 text-ink-gray-6"
      :text="row.description"
      :tip="row.description"
    />

    <div class="mt-3 flex items-center justify-between gap-3 border-t border-outline-gray-1 pt-2.5">
      <button
        type="button"
        class="inline-flex items-center gap-1 text-sm text-ink-gray-5 transition-colors hover:text-ink-gray-8"
        @click="emit('details')"
      >
        <span class="lucide-info size-3.5" aria-hidden="true" />{{ __('Learn more') }}
      </button>
      <Switch
        v-if="action.type === 'switch'"
        :model-value="row.enabled"
        :disabled="busy"
        :aria-label="__('Turn {0} on or off').format(row.label)"
        @update:model-value="(value) => emit(value ? 'connect' : 'disconnect')"
      />
      <Button v-else size="sm" :variant="action.variant" :loading="busy" :label="action.label" @click="emit(action.event)" />
    </div>
  </article>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { computed } from 'vue'
import { Button, Switch } from 'frappe-ui'
import IntegrationLogo from './IntegrationLogo.vue'
import { translate as __ } from '@/translation'

const props = defineProps({
  row: { type: Object, required: true },
  busy: { type: Boolean, default: false },
})

const emit = defineEmits(['connect', 'disconnect', 'details', 'setup'])

const live = computed(() => props.row.installed && props.row.enabled)

const subtitle = computed(() => {
  const sites = (props.row.where || []).filter((site) => site.ready)
  if (!live.value || !sites.length) return props.row.category
  if (sites.length > 1) return `${props.row.category} · ${__('{0} sites').format(sites.length)}`
  return `${props.row.category} · ${sites[0].remote ? sites[0].label : __('This site')}`
})

const status = computed(() => {
  if (live.value) return { label: __('Connected'), icon: 'lucide-check', class: 'bg-surface-green-1 text-ink-green-6' }
  if (!props.row.installed || props.row.setup) {
    return {
      label: props.row.setup ? __('Not set up') : __('Not installed'),
      icon: 'lucide-circle-dashed',
      class: 'bg-surface-gray-2 text-ink-gray-6',
    }
  }
  return { label: __('Off'), icon: 'lucide-circle-pause', class: 'bg-surface-gray-2 text-ink-gray-6' }
})

const action = computed(() => {
  if (props.row.setup) {
    return live.value
      ? { label: __('Manage'), variant: 'subtle', event: 'setup' }
      : { label: __('Set up'), variant: 'solid', event: 'setup' }
  }
  if (!props.row.installed) return { label: __('Install'), variant: 'subtle', event: 'details' }
  return { type: 'switch' }
})
</script>
