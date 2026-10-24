<template>
  <MessageField
    v-if="field.type === 'message'"
    :model-value="modelValue || ''"
    :label="__(field.label)"
    :description="description"
    :placeholder="field.placeholder"
    :required="field.required"
    :compact="!!field.compact"
    @update:model-value="update"
  />

  <ChoiceEditor
    v-else-if="field.type === 'options'"
    :model-value="modelValue || []"
    :label="__(field.label)"
    :required="field.required"
    :max="field.max || 3"
    :title-limit="field.titleLimit || 20"
    :with-description="!!field.withDescription"
    @update:model-value="update"
  />

  <RulesEditor
    v-else-if="field.type === 'rules'"
    :model-value="modelValue || {}"
    :label="__(field.label)"
    :required="field.required"
    :optional="!field.required"
    @update:model-value="update"
  />

  <TemplateParams
    v-else-if="field.type === 'template_params'"
    :model-value="modelValue || []"
    :template="config[field.templateKey] || ''"
    :label="__(field.label)"
    :scope="field.scope || ''"
    @update:model-value="update"
  />

  <FileField v-else-if="field.type === 'file'" :model-value="modelValue || ''" :label="__(field.label)" @update:model-value="update" />

  <AgentSelect
    v-else-if="field.type === 'agent'"
    :model-value="modelValue || ''"
    :label="__(field.label)"
    :required="field.required"
    @update:model-value="update"
  />

  <LinkField
    v-else-if="LINKS[field.type]"
    :model-value="modelValue"
    :doctype="LINKS[field.type]"
    :label="__(field.label)"
    :description="description"
    :required="field.required"
    @update:model-value="update"
  />

  <FormControl
    v-else-if="field.type === 'variable'"
    type="text"
    :model-value="modelValue ?? ''"
    :label="__(field.label)"
    :description="description || __('Use it later as {0}').format(variableToken(modelValue || field.placeholder || 'name'))"
    :placeholder="field.placeholder"
    :required="field.required"
    @update:model-value="(value) => update(slug(value))"
  />

  <FormControl
    v-else-if="field.type === 'time'"
    type="time"
    :model-value="modelValue ?? ''"
    :label="__(field.label)"
    :description="description"
    @update:model-value="update"
  />

  <LinkField
    v-else-if="field.type === 'doctype'"
    :model-value="modelValue"
    doctype="DocType"
    :filters="{ istable: 0 }"
    :label="__(field.label)"
    :description="description"
    :required="field.required"
    @update:model-value="update"
  />

  <LinkField
    v-else-if="field.type === 'template'"
    :model-value="modelValue"
    doctype="WhatsApp Templates"
    :label="__(field.label)"
    :description="description"
    :required="field.required"
    @update:model-value="update"
  />

  <FieldPicker
    v-else-if="field.type === 'field'"
    :model-value="modelValue || ''"
    :doctype="config[field.doctypeKey] || ''"
    :label="__(field.label)"
    :description="description"
    :required="field.required"
    @update:model-value="update"
  />

  <ExpressionField
    v-else-if="field.type === 'expression'"
    :model-value="modelValue ?? ''"
    :label="__(field.label)"
    :placeholder="field.placeholder"
    :required="field.required"
    :python="field.python"
    @update:model-value="update"
  />

  <KeyValueEditor
    v-else-if="field.type === 'keyvalue'"
    :model-value="modelValue || {}"
    :label="__(field.label)"
    :doctype="valuesDoctype"
    :key-label="__(field.keyLabel || 'Field')"
    :value-label="__(field.valueLabel || 'Value')"
    :key-placeholder="field.keyPlaceholder"
    :value-placeholder="field.valuePlaceholder"
    :show-required="!field.prefilled"
    :description="description"
    @update:model-value="update"
  />

  <PostPicker
    v-else-if="field.type === 'instagram_posts'"
    :model-value="modelValue || []"
    :label="__(field.label)"
    :description="description"
    @update:model-value="update"
  />

  <ListEditor
    v-else-if="field.type === 'list'"
    :model-value="modelValue || []"
    :label="__(field.label)"
    :placeholder="field.placeholder"
    @update:model-value="update"
  />

  <Switch
    v-else-if="field.type === 'switch'"
    :model-value="!!modelValue"
    :label="__(field.label)"
    :description="description"
    @update:model-value="update"
  />

  <Select
    v-else-if="field.type === 'select'"
    :model-value="modelValue"
    :label="__(field.label)"
    :description="description"
    :required="field.required"
    :options="options"
    :placeholder="__('Pick one')"
    @update:model-value="update"
  />

  <FormControl
    v-else
    :type="field.type === 'textarea' ? 'textarea' : field.type === 'number' ? 'number' : 'text'"
    :rows="4"
    :model-value="modelValue ?? ''"
    :label="__(field.label)"
    :description="description"
    :placeholder="field.placeholder"
    :required="field.required"
    @update:model-value="update"
  />
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { FormControl, Select, Switch } from 'frappe-ui'
import AgentSelect from './AgentSelect.vue'
import ChoiceEditor from './ChoiceEditor.vue'
import ExpressionField from './ExpressionField.vue'
import FileField from './FileField.vue'
import KeyValueEditor from './KeyValueEditor.vue'
import ListEditor from './ListEditor.vue'
import MessageField from './MessageField.vue'
import PostPicker from './PostPicker.vue'
import RulesEditor from './RulesEditor.vue'
import TemplateParams from './TemplateParams.vue'
import { doctypeFields } from './api'
import FieldPicker from '@/components/Automation/FieldPicker.vue'
import LinkField from '@/components/Common/LinkField.vue'
import { translate as __ } from '@/translation'

const props = defineProps({
  field: { type: Object, required: true },
  modelValue: { type: [String, Number, Boolean, Array, Object], default: null },
  config: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['update:modelValue'])

const LINKS = { form: 'WhatsApp Flow', label: 'OneChat Label', chat_link: 'OneChat Chat Link', team: 'OneChat Team' }

function variableToken(name) {
  return props.field.scope === 'records' ? `{{records.${name}.name}}` : `{{answers.${name}}}`
}

function slug(value) {
  return String(value || '')
    .toLowerCase()
    .replace(/[^a-z0-9_]+/g, '_')
    .replace(/^_+/, '')
}

const description = computed(() => (props.field.description ? __(props.field.description) : ''))

const options = computed(() =>
  (typeof props.field.options === 'function' ? props.field.options(props.config) : props.field.options || []).map((option) =>
    typeof option === 'string' ? { label: option, value: option } : { label: __(option.label), value: option.value },
  ),
)

const tableDoctype = ref('')

watch(
  () => (props.field.tableKey ? [props.config[props.field.doctypeKey], props.config[props.field.tableKey]] : []),
  async ([parent, table] = []) => {
    tableDoctype.value = ''
    if (!parent || !table) return
    try {
      tableDoctype.value = (await doctypeFields(parent)).find((row) => row.fieldname === table)?.options || ''
    } catch {
      tableDoctype.value = ''
    }
  },
  { immediate: true },
)

const valuesDoctype = computed(() => {
  if (props.field.tableKey) return tableDoctype.value
  if (props.field.doctypeOf) return props.field.doctypeOf(props.config)
  return props.field.fixedDoctype || (props.field.doctypeKey ? props.config[props.field.doctypeKey] || '' : '')
})

function update(value) {
  if (props.field.type === 'number') {
    emit('update:modelValue', value === '' || value === null ? '' : Number(value))
    return
  }
  if (props.field.type === 'switch') {
    emit('update:modelValue', value ? 1 : 0)
    return
  }

  emit('update:modelValue', value ?? '')
}
</script>
