<template>
  <div class="flex flex-col gap-4">
    <div class="flex flex-col gap-2 rounded-5 border border-outline-gray-2 p-3">
      <div class="flex items-center justify-between gap-2">
        <TruncatedText as="p" class="truncate text-base font-medium text-ink-gray-8" :text="form.flow_name" />
        <FormStatusBadge :status="form.status" size="sm" />
      </div>
      <p v-if="form.description" class="text-sm text-ink-gray-6">{{ form.description }}</p>
      <dl class="grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-1 text-sm">
        <dt class="text-ink-gray-5">{{ __('Account') }}</dt>
        <TruncatedText as="dd" class="truncate text-ink-gray-8" :text="form.whatsapp_account || '—'" />
        <dt class="text-ink-gray-5">{{ __('Category') }}</dt>
        <TruncatedText as="dd" class="truncate text-ink-gray-8" :text="categoryLabel(form.category) || '—'" />
        <dt class="text-ink-gray-5">{{ __('Button text') }}</dt>
        <TruncatedText as="dd" class="truncate text-ink-gray-8" :text="form.flow_cta || '—'" />
      </dl>
    </div>

    <div v-for="(screen, index) in screens" :key="screen.key" class="flex flex-col gap-1.5">
      <p class="flex items-center gap-2 text-sm font-medium text-ink-gray-7">
        <span class="flex size-5 items-center justify-center rounded-full bg-surface-gray-2 text-xs text-ink-gray-6">{{ index + 1 }}</span>
        {{ screen.screen_title || screen.screen_id }}
        <span v-if="screen.terminal" class="lucide-flag size-3.5 text-ink-green-6" :aria-label="__('Final screen')" />
      </p>
      <ul class="flex flex-col divide-y divide-outline-gray-1 rounded-4 border border-outline-gray-1">
        <li v-for="field in screen.fields.filter((item) => item.enabled)" :key="field.key" class="flex items-center gap-2 px-3 py-2">
          <span :class="fieldDef(field.field_type).icon" class="size-3.5 shrink-0 text-ink-gray-5" aria-hidden="true" />
          <TruncatedText
            class="min-w-0 flex-1 truncate text-sm text-ink-gray-8"
            :text="field.label || field.field_name || __(fieldDef(field.field_type).label)"
          />
          <span v-if="field.required" class="text-xs text-ink-gray-5">{{ __('Required') }}</span>
        </li>
        <li v-if="!screen.fields.length" class="px-3 py-2 text-sm text-ink-gray-4">{{ __('No fields') }}</li>
      </ul>
    </div>
  </div>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import FormStatusBadge from './FormStatusBadge.vue'
import { categoryLabel, fieldDef } from './formSchema'
import { translate as __ } from '@/translation'

defineProps({
  form: { type: Object, required: true },
  screens: { type: Array, default: () => [] },
})
</script>
