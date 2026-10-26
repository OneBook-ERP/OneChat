<template>
  <div class="flex flex-col gap-4">
    <LinkField
      :model-value="form.whatsapp_account"
      doctype="OneChat Account"
      :filters="accountFilters"
      :label="__('WhatsApp account')"
      :required="true"
      :disabled="!!form.flow_id"
      :description="form.flow_id ? __('The form already exists on this account in Meta.') : ''"
      @update:model-value="(value) => emit('change', { whatsapp_account: value || '' })"
    />
    <FormControl
      type="select"
      :label="__('Category')"
      :required="true"
      :options="CATEGORIES.map((value) => ({ label: categoryLabel(value), value }))"
      :model-value="form.category"
      @update:model-value="(value) => emit('change', { category: value })"
    />
    <FormControl
      type="textarea"
      :rows="3"
      :label="__('Description')"
      :placeholder="__('What this form is for, for your team')"
      :model-value="form.description"
      @update:model-value="(value) => emit('change', { description: value })"
    />
    <FormControl
      type="text"
      :label="__('Button text')"
      :description="__('The button customers tap in the chat to open the form')"
      :model-value="form.flow_cta"
      :maxlength="20"
      @update:model-value="(value) => emit('change', { flow_cta: value })"
    />
    <FormControl
      type="select"
      :label="__('Flow JSON version')"
      :options="VERSIONS.map((value) => ({ label: value, value }))"
      :model-value="form.data_api_version"
      @update:model-value="(value) => emit('change', { data_api_version: value })"
    />
    <FormControl
      type="url"
      :label="__('Data endpoint URL')"
      :description="__('Only for forms that load data from your server while they are open')"
      :model-value="form.endpoint_uri"
      @update:model-value="(value) => emit('change', { endpoint_uri: value })"
    />

    <dl v-if="form.name" class="grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-1.5 rounded-4 bg-surface-gray-1 p-3 text-sm">
      <dt class="text-ink-gray-5">{{ __('Meta ID') }}</dt>
      <TruncatedText as="dd" class="truncate text-ink-gray-8" :text="form.flow_id || __('Not created yet')" />
      <dt class="text-ink-gray-5">{{ __('Status') }}</dt>
      <dd><FormStatusBadge :status="form.status" size="sm" /></dd>
      <dt class="text-ink-gray-5">{{ __('Updated') }}</dt>
      <TruncatedText as="dd" class="truncate text-ink-gray-8" :text="formatDateTime(form.modified)" />
    </dl>
  </div>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { computed } from 'vue'
import { FormControl } from 'frappe-ui'
import LinkField from '@/components/Common/LinkField.vue'
import FormStatusBadge from './FormStatusBadge.vue'
import { CATEGORIES, VERSIONS, categoryLabel } from './formSchema'
import { formatDateTime } from '@/utils/format'
import { useNumbers } from '@/stores/numbers'
import { translate as __ } from '@/translation'

defineProps({
  form: { type: Object, required: true },
})

const emit = defineEmits(['change'])

const numbers = useNumbers()
if (!numbers.loaded) numbers.load()

const accountFilters = computed(() => ({
  channel: ['!=', 'Instagram'],
  status: 'Active',
  ...(numbers.hidden.length ? { name: ['not in', numbers.hidden] } : {}),
}))
</script>
