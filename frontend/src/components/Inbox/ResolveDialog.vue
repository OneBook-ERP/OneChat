<template>
  <ResponsiveDialog v-model:open="open" :title="count > 1 ? __('Resolve {0} chats').format(count) : __('Resolve chat')" size="md">
    <template #default>
      <div class="flex flex-col gap-4">
        <div v-if="waiting" class="flex items-start gap-2 rounded-4 bg-surface-amber-1 p-3 text-sm text-ink-amber-7">
          <span class="lucide-message-circle-warning mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <span>{{
            count > 1
              ? __('Some customers are waiting for a reply.')
              : __('The customer is waiting for a reply. Resolve only if nothing more is needed.')
          }}</span>
        </div>

        <div v-if="rules.require_reason" class="flex flex-col gap-1.5">
          <FormLabel :label="__('Why is it resolved?')" required />
          <div v-if="rules.reasons.length" class="flex flex-wrap gap-1.5">
            <Button
              v-for="item in rules.reasons"
              :key="item"
              :variant="reason === item ? 'solid' : 'subtle'"
              :label="__(item)"
              @click="reason = item"
            />
          </div>
          <FormControl v-else v-model="reason" type="text" :placeholder="__('Question answered')" />
        </div>

        <FormControl
          v-model="note"
          type="textarea"
          :rows="2"
          :label="rules.require_note ? __('Note') : __('Note (optional)')"
          :required="rules.require_note"
          :placeholder="__('What was done for the customer')"
        />
      </div>
    </template>
    <template #actions>
      <div class="flex justify-end gap-2">
        <Button variant="subtle" :label="__('Cancel')" @click="open = false" />
        <Button
          variant="solid"
          icon-left="lucide-circle-check"
          :label="waiting ? __('Resolve anyway') : __('Resolve')"
          :disabled="(rules.require_reason && !reason.trim()) || (rules.require_note && !note.trim())"
          :loading="busy"
          @click="emit('confirm', { reason: reason.trim(), note: note.trim(), force: 1 })"
        />
      </div>
    </template>
  </ResponsiveDialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { Button, FormControl, FormLabel } from 'frappe-ui'
import ResponsiveDialog from '@/components/Common/ResponsiveDialog.vue'
import { translate as __ } from '@/translation'

defineProps({
  rules: { type: Object, required: true },
  waiting: { type: Boolean, default: false },
  count: { type: Number, default: 1 },
  busy: { type: Boolean, default: false },
})

const emit = defineEmits(['confirm'])
const open = defineModel('open', { type: Boolean, default: false })

const reason = ref('')
const note = ref('')

watch(open, (value) => {
  if (!value) return
  reason.value = ''
  note.value = ''
})
</script>
