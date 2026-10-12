<template>
  <ResponsiveDialog v-model:open="open" :title="__('Run for real')" size="xl">
    <template #default>
      <div class="flex flex-col gap-4">
        <p class="text-base text-ink-gray-7">
          {{
            __(
              'The flow runs for real on the server. Messages are really sent and records really change. Use Test chat to try it without sending anything.',
            )
          }}
        </p>

        <LinkField
          v-if="kind !== 'scheduled_trigger'"
          :model-value="contact"
          doctype="OneChat Contact"
          :label="__('Run for this contact')"
          :description="__('Pick yourself to receive the messages on your phone. Replies continue the flow like a real customer would.')"
          @update:model-value="(value) => (contact = value || '')"
        />

        <LinkField
          v-if="doctype"
          :model-value="docname"
          :doctype="doctype"
          :label="__('Fill from a {0}').format(__(doctype))"
          :description="__('Loads the document into the context, the way a real event would.')"
          @update:model-value="loadDocument"
        />

        <div class="flex flex-col gap-1.5">
          <FormControl v-model="text" type="textarea" class="font-mono" :rows="12" :label="__('Context (JSON)')" />
          <ErrorMessage :message="error" />
        </div>
      </div>
    </template>

    <template #actions>
      <div class="flex w-full justify-end gap-2">
        <Button variant="subtle" :label="__('Cancel')" @click="open = false" />
        <Button variant="solid" icon-left="lucide-play" :loading="running" :label="__('Run now')" @click="run" />
      </div>
    </template>
  </ResponsiveDialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Button, ErrorMessage, FormControl, call } from 'frappe-ui'
import ResponsiveDialog from '@/components/Common/ResponsiveDialog.vue'
import { nodeDef } from './nodeTypes'
import LinkField from '@/components/Common/LinkField.vue'
import { errorMessage } from '@/utils/format'
import { translate as __ } from '@/translation'

const props = defineProps({
  trigger: { type: Object, default: null },
  running: { type: Boolean, default: false },
})

const emit = defineEmits(['run'])

const open = defineModel('open', { type: Boolean, default: false })

const text = ref('{}')
const error = ref('')
const docname = ref('')
const contact = ref('')

const kind = computed(() => nodeDef(props.trigger?.data?.nodeType).type)
const doctype = computed(() => (kind.value === 'doc_event_trigger' ? props.trigger.data.config?.doctype || '' : ''))

function sample(doc = {}) {
  if (kind.value === 'doc_event_trigger') {
    return {
      erp: { doctype: doctype.value, name: doc.name || '', doc },
      trigger: 'erpnext_event',
      vars: {},
    }
  }
  if (['message_received', 'button_clicked', 'whatsapp_trigger'].includes(kind.value)) {
    return {
      message: { type: 'text', text: '' },
      trigger: 'message',
      vars: {},
    }
  }

  return { trigger: 'test', vars: {} }
}

watch(open, (value) => {
  if (!value) return

  error.value = ''
  docname.value = ''
  text.value = JSON.stringify(sample(), null, 2)
})

async function loadDocument(name) {
  docname.value = name || ''
  if (!name) return

  try {
    const doc = await call('frappe.client.get', { doctype: doctype.value, name })
    text.value = JSON.stringify(sample(doc), null, 2)
    error.value = ''
  } catch (err) {
    error.value = errorMessage(err)
  }
}

function run() {
  let context
  try {
    context = JSON.parse(text.value || '{}')
  } catch {
    error.value = __('The context is not valid JSON.')
    return
  }

  error.value = ''
  emit('run', context, contact.value || null)
}
</script>
