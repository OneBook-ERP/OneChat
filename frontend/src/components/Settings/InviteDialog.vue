<template>
  <ResponsiveDialog v-model:open="open" :title="__('Invite a member')" size="md">
    <template #default>
      <div class="grid grid-cols-2 gap-4">
        <FormControl v-model="form.email" class="col-span-2" type="email" :label="__('Email')" placeholder="name@company.com" required />
        <FormControl v-model="form.first_name" class="col-span-2 sm:col-span-1" :label="__('First name')" />
        <FormControl v-model="form.last_name" class="col-span-2 sm:col-span-1" :label="__('Last name')" />
      </div>
      <p class="mt-3 text-sm text-ink-gray-5">
        {{ __('New people get a welcome email to set their password. Existing users are added to OneChat as agents.') }}
      </p>
      <ErrorMessage :message="error" class="mt-3" />
    </template>

    <template #actions>
      <div class="flex justify-end gap-2">
        <Button variant="subtle" :label="__('Cancel')" @click="open = false" />
        <Button variant="solid" :label="__('Send invite')" :loading="sending" @click="invite" />
      </div>
    </template>
  </ResponsiveDialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { Button, ErrorMessage, FormControl, call, toast } from 'frappe-ui'
import ResponsiveDialog from '@/components/Common/ResponsiveDialog.vue'
import { errorMessage } from '@/utils/format'
import { translate as __ } from '@/translation'

const emit = defineEmits(['invited'])

const open = defineModel('open', { type: Boolean, default: false })

const form = ref({ email: '', first_name: '', last_name: '' })
const sending = ref(false)
const error = ref('')

watch(open, (value) => {
  if (!value) return

  form.value = { email: '', first_name: '', last_name: '' }
  error.value = ''
})

async function invite() {
  const email = form.value.email.trim()
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    error.value = __('Enter a valid email address')
    return
  }

  sending.value = true
  error.value = ''

  try {
    const result = await call('onechat.workspace.users.create_user', {
      email,
      first_name: form.value.first_name.trim() || email.split('@')[0],
      last_name: form.value.last_name.trim() || null,
    })
    toast.success(__(result?.message || 'Invitation sent'))
    emit('invited')
    open.value = false
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    sending.value = false
  }
}
</script>
