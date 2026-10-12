<template>
  <ResponsiveDialog v-model:open="open" :title="__('Send a test')" size="md">
    <template #default>
      <div class="flex flex-col gap-4">
        <p class="text-sm text-ink-gray-5">
          {{
            status === 'Published'
              ? __('Sends the form to this number as a WhatsApp message.')
              : __('Draft forms are sent in test mode. Only numbers that can test your WhatsApp app will be able to open it.')
          }}
        </p>
        <PhoneField v-model="phone" :label="__('Phone number')" required />
        <FormControl v-model="message" type="textarea" :rows="2" :label="__('Message')" :placeholder="__('Test: {0}').format(formName)" />
        <ErrorMessage :message="error" />
      </div>
    </template>

    <template #actions>
      <div class="flex w-full justify-end gap-2">
        <Button variant="subtle" :label="__('Cancel')" @click="open = false" />
        <Button
          variant="solid"
          icon-left="lucide-send"
          :loading="sending"
          :disabled="!phone.replace(/\D/g, '')"
          :label="__('Send')"
          @click="send"
        />
      </div>
    </template>
  </ResponsiveDialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { Button, ErrorMessage, FormControl, call, toast } from 'frappe-ui'
import PhoneField from '@/components/Common/PhoneField.vue'
import ResponsiveDialog from '@/components/Common/ResponsiveDialog.vue'
import { docMethod } from './formSchema'
import { errorMessage } from '@/utils/format'
import { translate as __ } from '@/translation'

const props = defineProps({
  name: { type: String, default: null },
  formName: { type: String, default: '' },
  status: { type: String, default: 'Draft' },
})

const open = defineModel('open', { type: Boolean, default: false })

const STORAGE_KEY = 'onechat.forms.testPhone'

const phone = ref(readPhone())
const message = ref('')
const sending = ref(false)
const error = ref('')

function readPhone() {
  try {
    return localStorage.getItem(STORAGE_KEY) || ''
  } catch {
    return ''
  }
}

function rememberPhone(number) {
  try {
    localStorage.setItem(STORAGE_KEY, number)
  } catch {
    return
  }
}

async function send() {
  const number = phone.value.replace(/\D/g, '')
  if (!number || !props.name) return

  sending.value = true
  error.value = ''
  try {
    await call('run_doc_method', docMethod(props.name, 'send_test', { phone_number: number, message: message.value.trim() || null }))
    rememberPhone(number)
    toast.success(__('Test sent to {0}').format(number))
    open.value = false
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    sending.value = false
  }
}

watch(open, (value) => {
  if (value) error.value = ''
})
</script>
