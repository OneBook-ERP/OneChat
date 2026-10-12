<template>
  <SettingsHeader :title="__('Profile')" :description="__('How your teammates and customers see you')">
    <template #actions>
      <Button variant="solid" :label="__('Save')" :loading="saving" :disabled="loading || !dirty" @click="save" />
    </template>
  </SettingsHeader>

  <SettingsBody>
    <div v-if="loading" class="flex flex-col gap-4 pt-6">
      <Skeleton class="size-16 rounded-full" />
      <Skeleton v-for="row in 3" :key="row" class="h-9 w-full" />
    </div>

    <div v-else class="flex flex-col gap-6 pt-6">
      <div class="flex flex-wrap items-center gap-4">
        <Avatar size="3xl" :image="doc.user_image" :label="doc.full_name || doc.name" />
        <div class="flex flex-wrap items-center gap-2">
          <FileUploader
            :file-types="['image/*']"
            :private="false"
            doctype="User"
            :docname="doc.name"
            fieldname="user_image"
            @success="setPhoto"
          >
            <template #default="{ uploading, progress, openFileSelector }">
              <Button
                icon-left="lucide-upload"
                :loading="uploading"
                :label="uploading ? __('Uploading {0}%').format(progress) : __('Upload photo')"
                @click="openFileSelector"
              />
            </template>
          </FileUploader>
          <Button v-if="doc.user_image" variant="ghost" :label="__('Remove')" :loading="photoSaving" @click="removePhoto" />
        </div>
      </div>

      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <FormControl v-model="form.first_name" :label="__('First name')" required />
        <FormControl v-model="form.last_name" :label="__('Last name')" />
        <FormControl class="sm:col-span-2" :model-value="doc.email || doc.name" :label="__('Email')" disabled />
      </div>

      <div>
        <p class="mb-2 text-sm text-ink-gray-5">{{ __('Roles') }}</p>
        <div class="flex flex-wrap gap-1.5">
          <Badge v-for="role in roles" :key="role" theme="gray" variant="subtle" :label="__(role)" />
          <span v-if="!roles.length" class="text-base text-ink-gray-5">{{ __('No OneChat roles') }}</span>
        </div>
      </div>

      <div class="flex items-center justify-between gap-3 rounded-4 border border-outline-gray-1 px-3 py-2.5">
        <div class="min-w-0">
          <p class="text-base font-medium text-ink-gray-8">{{ __('Time off') }}</p>
          <p class="text-sm text-ink-gray-5">{{ __('Add your leave so new chats are not assigned to you while you are away.') }}</p>
        </div>
        <Button variant="subtle" icon-left="lucide-plane" :label="__('Manage')" @click="leaveOpen = true" />
      </div>

      <ErrorMessage :message="error" />
    </div>
    <ScheduleDialog v-model:open="leaveOpen" leave-only />
  </SettingsBody>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import {
  Avatar,
  Badge,
  Button,
  ErrorMessage,
  FileUploader,
  FormControl,
  SettingsBody,
  SettingsHeader,
  Skeleton,
  call,
  toast,
} from 'frappe-ui'
import ScheduleDialog from './ScheduleDialog.vue'
import { session } from '@/data/session'
import { errorMessage } from '@/utils/format'
import { translate as __ } from '@/translation'

const APP_ROLES = ['OneChat Agent', 'OneChat Admin', 'OneChat Manager', 'System Manager']

const leaveOpen = ref(false)

const doc = ref({})
const form = ref({ first_name: '', last_name: '' })
const loading = ref(true)
const saving = ref(false)
const photoSaving = ref(false)
const error = ref('')

const dirty = computed(
  () => (form.value.first_name || '') !== (doc.value.first_name || '') || (form.value.last_name || '') !== (doc.value.last_name || ''),
)

const roles = computed(() => {
  const mine = (doc.value.roles || []).map((row) => row.role)

  return APP_ROLES.filter((role) => mine.includes(role))
})

function adopt(value) {
  doc.value = value
  form.value = { first_name: value.first_name || '', last_name: value.last_name || '' }
  Object.assign(session.user, { full_name: value.full_name, image: value.user_image || null })
}

async function load() {
  loading.value = true
  error.value = ''

  try {
    adopt(await call('frappe.client.get', { doctype: 'User', name: session.user.name }))
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    loading.value = false
  }
}

async function update(fieldname) {
  const saved = await call('frappe.client.set_value', { doctype: 'User', name: doc.value.name, fieldname })
  adopt({ ...doc.value, ...saved, roles: doc.value.roles })
}

async function save() {
  if (!form.value.first_name?.trim()) {
    error.value = __('Fill in {0}').format(__('First name'))
    return
  }

  saving.value = true
  error.value = ''

  try {
    await update({ first_name: form.value.first_name.trim(), last_name: form.value.last_name?.trim() || '' })
    toast.success(__('Profile saved'))
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    saving.value = false
  }
}

async function setPhoto(file) {
  error.value = ''

  try {
    await update({ user_image: file.file_url })
    toast.success(__('Photo updated'))
  } catch (err) {
    error.value = errorMessage(err)
  }
}

async function removePhoto() {
  photoSaving.value = true
  error.value = ''

  try {
    await update({ user_image: '' })
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    photoSaving.value = false
  }
}

onMounted(load)
</script>
