<template>
  <div class="flex h-full flex-col">
    <div class="border-b border-outline-gray-1 p-3">
      <p class="text-base font-medium text-ink-gray-8">{{ __('Flow settings') }}</p>
      <p class="text-xs text-ink-gray-5">{{ __('Select a step or connection to configure it.') }}</p>
    </div>

    <ScrollArea class="min-h-0 flex-1" viewport-class="p-3">
      <div class="flex flex-col gap-4">
        <FormControl
          type="textarea"
          :rows="3"
          :label="__('Description')"
          :model-value="flow.description || ''"
          :placeholder="__('What this flow does, for your team')"
          @update:model-value="(value) => emit('change', { description: value })"
        />
        <Select
          :label="__('Category')"
          :model-value="flow.category || ''"
          :placeholder="__('Pick a category')"
          :options="FLOW_CATEGORIES.map((value) => ({ label: __(value), value }))"
          @update:model-value="(value) => emit('change', { category: value })"
        />
        <div class="flex flex-col gap-3 rounded-4 border border-outline-gray-1 p-3">
          <Switch
            :model-value="!!flow.stop_on_agent_reply"
            :label="__('Stop when an agent replies')"
            :description="__('The bot steps aside as soon as someone from the team writes in the chat.')"
            @update:model-value="(value) => emit('change', { stop_on_agent_reply: value ? 1 : 0 })"
          />
          <FormControl
            type="number"
            :label="__('Wait for replies (hours)')"
            :description="__('After this, a question or menu gives up and follows its No reply path.')"
            :model-value="flow.reply_timeout_hours || 24"
            @update:model-value="(value) => emit('change', { reply_timeout_hours: Number(value) || 24 })"
          />
        </div>

        <div class="flex flex-col gap-3 rounded-4 border border-outline-gray-1 p-3">
          <div>
            <p class="text-base font-medium text-ink-gray-8">{{ __('When a step fails') }}</p>
            <p class="text-xs text-ink-gray-5">
              {{ __('Used when a step fails and has no On error path, so the customer is never left waiting.') }}
            </p>
          </div>
          <FormControl
            type="textarea"
            :rows="3"
            :label="__('Message to the customer')"
            :placeholder="__('Leave empty to send nothing')"
            :model-value="flow.error_message || ''"
            @update:model-value="(value) => emit('change', { error_message: value })"
          />
          <Switch
            :model-value="!!flow.error_handover"
            :label="__('Hand over to an agent')"
            :description="__('Stop the bot, leave a note with the error, and assign the chat if nobody has it.')"
            @update:model-value="(value) => emit('change', { error_handover: value ? 1 : 0 })"
          />
          <Select
            v-if="flow.error_handover"
            :label="__('Assign to')"
            :model-value="flow.error_team || ''"
            :options="teamOptions"
            @update:model-value="(value) => emit('change', { error_team: value || '' })"
          />
          <Switch
            :model-value="!!flow.error_notify"
            :label="__('Alert admins')"
            :description="__('When this flow fails 5 times within an hour.')"
            @update:model-value="(value) => emit('change', { error_notify: value ? 1 : 0 })"
          />
          <Switch
            :model-value="!!flow.error_pause"
            :label="__('Pause the flow')"
            :description="__('Turn it off automatically after 5 failures within an hour.')"
            @update:model-value="(value) => emit('change', { error_pause: value ? 1 : 0 })"
          />
        </div>

        <div class="grid grid-cols-2 gap-2">
          <div class="rounded-4 bg-surface-gray-2 px-3 py-2">
            <p class="text-xs text-ink-gray-5">{{ __('Steps') }}</p>
            <p class="text-lg font-medium text-ink-gray-8">{{ stepCount }}</p>
          </div>
          <div class="rounded-4 bg-surface-gray-2 px-3 py-2">
            <p class="text-xs text-ink-gray-5">{{ __('Connections') }}</p>
            <p class="text-lg font-medium text-ink-gray-8">{{ edgeCount }}</p>
          </div>
        </div>

        <div class="flex flex-col gap-2 text-sm text-ink-gray-6">
          <p class="font-medium text-ink-gray-7">{{ __('Tips') }}</p>
          <p class="flex gap-2">
            <span class="lucide-mouse-pointer-click mt-0.5 size-4 shrink-0 text-ink-gray-4" aria-hidden="true" />
            {{ __('Drag from a dot on a step to another step to connect them. Buttons and answers each have their own dot.') }}
          </p>
          <p class="flex gap-2">
            <span class="lucide-smartphone mt-0.5 size-4 shrink-0 text-ink-gray-4" aria-hidden="true" />
            {{ __('Use Test chat to try the flow as a customer. Nothing is sent.') }}
          </p>
          <p class="flex gap-2">
            <span class="lucide-keyboard mt-0.5 size-4 shrink-0 text-ink-gray-4" aria-hidden="true" />
            {{ __('Delete or Backspace removes the selection. Ctrl+S saves.') }}
          </p>
        </div>
      </div>
    </ScrollArea>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { FormControl, ScrollArea, Select, Switch, call } from 'frappe-ui'
import { FLOW_CATEGORIES } from './nodeTypes'
import { translate as __ } from '@/translation'

defineProps({
  flow: { type: Object, required: true },
  stepCount: { type: Number, default: 0 },
  edgeCount: { type: Number, default: 0 },
})

const emit = defineEmits(['change'])

const teams = ref([])

const teamOptions = computed(() => [
  { label: __('Next available agent'), value: '' },
  ...teams.value.map((name) => ({ label: __('Next available in {0}').format(name), value: name })),
])

onMounted(async () => {
  try {
    teams.value = await call('frappe.client.get_list', {
      doctype: 'OneChat Team',
      fields: ['name'],
      limit_page_length: 0,
      order_by: 'name asc',
    }).then((rows) => rows.map((row) => row.name))
  } catch {
    teams.value = []
  }
})
</script>
