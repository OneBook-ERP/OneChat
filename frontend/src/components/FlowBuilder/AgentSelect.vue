<template>
  <Select
    :model-value="modelValue"
    :label="label"
    :required="required"
    :options="options"
    :placeholder="__('Pick an agent')"
    @update:model-value="(value) => emit('update:modelValue', value)"
  />
</template>

<script setup>
import { computed } from 'vue'
import { Select, createResource } from 'frappe-ui'
import { translate as __ } from '@/translation'

defineProps({
  modelValue: { type: String, default: '' },
  label: { type: String, default: '' },
  required: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue'])

const agents = createResource({ url: 'onechat.inbox.conversations.agents', auto: true, cache: 'onechat-flow-agents' })

const options = computed(() => (agents.data || []).map((row) => ({ label: row.full_name || row.name, value: row.name })))
</script>
