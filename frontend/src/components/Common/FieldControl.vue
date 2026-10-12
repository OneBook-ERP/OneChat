<template>
  <div v-if="field.type === 'check'" class="flex items-center justify-between gap-4 py-1">
    <div class="flex min-w-0 items-center gap-1">
      <TruncatedText as="p" class="truncate text-base text-ink-gray-8" :text="__(field.label)" />
      <InfoHint v-if="field.description" :text="__(field.description)" :title="__(field.label)" />
    </div>
    <Switch :model-value="!!modelValue" :disabled="field.readOnly" @update:model-value="(value) => update(value ? 1 : 0)" />
  </div>

  <div v-else>
    <FieldLabel :label="__(field.label)" :description="field.description ? __(field.description) : ''" :required="!!field.required" />

    <LinkField
      v-if="field.type === 'link'"
      :model-value="modelValue"
      :doctype="field.options"
      :filters="field.filters || {}"
      :disabled="field.readOnly"
      @update:model-value="update"
    />

    <PhoneField
      v-else-if="field.type === 'phone'"
      :model-value="modelValue || ''"
      :placeholder="field.placeholder ? __(field.placeholder) : ''"
      :disabled="field.readOnly"
      @update:model-value="update"
    />

    <Password
      v-else-if="field.type === 'password'"
      :placeholder="field.placeholder ? __(field.placeholder) : undefined"
      :disabled="field.readOnly"
      :model-value="modelValue || ''"
      @update:model-value="update"
    />

    <FormControl
      v-else
      :type="controlType"
      :placeholder="field.placeholder ? __(field.placeholder) : undefined"
      :disabled="field.readOnly"
      :options="options"
      :rows="field.rows || (field.type === 'code' ? 8 : 4)"
      :class="{ 'font-mono': field.type === 'code' }"
      :model-value="modelValue"
      @update:model-value="update"
    />
  </div>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { computed } from 'vue'
import { FormControl, Password, Switch } from 'frappe-ui'
import FieldLabel from './FieldLabel.vue'
import InfoHint from './InfoHint.vue'
import LinkField from './LinkField.vue'
import PhoneField from './PhoneField.vue'
import { translate as __ } from '@/translation'

const props = defineProps({
  field: { type: Object, required: true },
  modelValue: { type: [String, Number, Boolean, Array, Object], default: null },
})

const emit = defineEmits(['update:modelValue'])

const TYPES = {
  data: 'text',
  email: 'email',
  phone: 'tel',
  url: 'url',
  int: 'number',
  float: 'number',
  textarea: 'textarea',
  code: 'textarea',
  select: 'select',
  date: 'date',
  datetime: 'datetime',
}

const controlType = computed(() => TYPES[props.field.type] || 'text')

const options = computed(() =>
  (props.field.options && Array.isArray(props.field.options) ? props.field.options : []).map((option) =>
    typeof option === 'string' ? { label: __(option), value: option } : option,
  ),
)

function update(value) {
  if (['int', 'float'].includes(props.field.type) && value !== '' && value !== null) {
    emit('update:modelValue', Number(value))
    return
  }

  emit('update:modelValue', value)
}
</script>
