<template>
  <div class="flex flex-col gap-6 pt-6">
    <div v-if="loading" class="flex flex-col gap-3">
      <Skeleton class="size-20 rounded-full" />
      <Skeleton v-for="row in 5" :key="row" class="h-9 w-full" />
    </div>

    <template v-else-if="profile">
      <ErrorMessage :message="error" />

      <div class="flex flex-wrap items-center gap-4">
        <Avatar :image="profile.profile_picture_url" :label="business || __('Business')" size="3xl" />
        <div class="min-w-0 flex-1">
          <TruncatedText as="p" class="truncate text-lg font-semibold text-ink-gray-8" :text="business || __('Your business')" />
          <p class="mt-0.5 text-sm text-ink-gray-5">
            {{ __('Customers see this profile when they tap your name in WhatsApp.') }}
          </p>
        </div>
        <FileUploader
          v-if="profile.can_upload"
          :file-types="['image/jpeg', 'image/png']"
          :validate-file="checkPhoto"
          @success="uploadPhoto"
        >
          <template #default="{ openFileSelector, uploading }">
            <Button icon-left="lucide-camera" :loading="uploading || photoSaving" :label="__('Change photo')" @click="openFileSelector" />
          </template>
        </FileUploader>
        <Tooltip v-else :text="__('Add the App ID in Setup to change the photo')">
          <Button icon-left="lucide-camera" :label="__('Change photo')" disabled />
        </Tooltip>
      </div>

      <div class="grid grid-cols-2 gap-x-4 gap-y-4">
        <div class="col-span-2">
          <FormControl v-model="form.about" :label="__('About')" :placeholder="__('Hey there! We are on WhatsApp.')" :maxlength="139" />
          <p class="mt-1 text-right text-xs tabular-nums text-ink-gray-4">{{ form.about.length }} / 139</p>
        </div>
        <div class="col-span-2">
          <FormControl
            v-model="form.description"
            type="textarea"
            :rows="3"
            :label="__('Description')"
            :placeholder="__('What your business does')"
            :maxlength="512"
          />
          <p class="mt-1 text-right text-xs tabular-nums text-ink-gray-4">{{ form.description.length }} / 512</p>
        </div>
        <div class="col-span-2 sm:col-span-1">
          <FormControl v-model="form.vertical" type="select" :label="__('Category')" :options="verticals" />
        </div>
        <div class="col-span-2 sm:col-span-1">
          <FormControl v-model="form.email" type="email" :label="__('Email')" :maxlength="128" />
        </div>
        <div class="col-span-2">
          <FormControl v-model="form.address" :label="__('Address')" :maxlength="256" />
        </div>
        <div v-for="(site, index) in form.websites" :key="index" class="col-span-2 sm:col-span-1">
          <FormControl
            v-model="form.websites[index]"
            type="url"
            :label="index ? __('Second website') : __('Website')"
            placeholder="https://"
          />
        </div>
      </div>

      <div class="flex items-center justify-end gap-2">
        <Button variant="subtle" :label="__('Reset')" :disabled="!dirty || saving" @click="reset" />
        <Button variant="solid" :label="__('Save profile')" :loading="saving" :disabled="!dirty" @click="save" />
      </div>
    </template>

    <EmptyState
      v-else
      icon="lucide-store"
      :title="__('Could not load the profile')"
      :description="error || __('Test the connection in Setup first.')"
    >
      <Button variant="subtle" :label="__('Try again')" @click="load" />
    </EmptyState>
  </div>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { computed, onMounted, reactive, ref } from 'vue'
import { Avatar, Button, ErrorMessage, FileUploader, FormControl, Skeleton, Tooltip, call, toast } from 'frappe-ui'
import EmptyState from '@/components/Common/EmptyState.vue'
import { errorMessage } from '@/utils/format'
import { translate as __ } from '@/translation'

const props = defineProps({
  name: { type: String, required: true },
  business: { type: String, default: '' },
})

const CATEGORIES = {
  UNDEFINED: 'Not set',
  OTHER: 'Other',
  AUTO: 'Automotive',
  BEAUTY: 'Beauty, spa and salon',
  APPAREL: 'Clothing and apparel',
  EDU: 'Education',
  ENTERTAIN: 'Entertainment',
  EVENT_PLAN: 'Event planning and service',
  FINANCE: 'Finance and banking',
  GROCERY: 'Food and grocery',
  GOVT: 'Public service',
  HOTEL: 'Hotel and lodging',
  HEALTH: 'Medical and health',
  NONPROFIT: 'Non-profit',
  PROF_SERVICES: 'Professional services',
  RETAIL: 'Shopping and retail',
  TRAVEL: 'Travel and transportation',
  RESTAURANT: 'Restaurant',
  NOT_A_BIZ: 'Not a business',
}
const FIELDS = ['about', 'description', 'vertical', 'email', 'address']
const MAX_PHOTO = 5 * 1024 * 1024

const profile = ref(null)
const form = reactive({ about: '', description: '', vertical: 'UNDEFINED', email: '', address: '', websites: ['', ''] })
const loading = ref(true)
const saving = ref(false)
const photoSaving = ref(false)
const error = ref('')

const verticals = computed(() =>
  (profile.value?.verticals || Object.keys(CATEGORIES)).map((value) => ({ label: __(CATEGORIES[value] || value), value })),
)

const dirty = computed(
  () =>
    !!profile.value &&
    (FIELDS.some((field) => (form[field] || '') !== (profile.value[field] || '')) ||
      form.websites.some((site, index) => (site || '') !== (profile.value.websites[index] || ''))),
)

function reset() {
  for (const field of FIELDS) form[field] = profile.value[field] || ''
  form.websites = [...profile.value.websites]
}

function apply(data) {
  profile.value = data
  reset()
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    apply(await call('onechat.whatsapp.accounts.profile', { name: props.name }))
  } catch (err) {
    profile.value = null
    error.value = errorMessage(err)
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  error.value = ''
  try {
    apply(await call('onechat.whatsapp.accounts.save_profile', { name: props.name, values: { ...form } }))
    toast.success(__('Profile updated on WhatsApp'))
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    saving.value = false
  }
}

function checkPhoto(file) {
  if (file.size <= MAX_PHOTO) return

  const message = __('Use an image under 5 MB.')
  toast.error(message)
  return message
}

async function uploadPhoto(file) {
  photoSaving.value = true
  error.value = ''
  try {
    apply(await call('onechat.whatsapp.accounts.upload_photo', { name: props.name, file_url: file.file_url }))
    toast.success(__('Profile photo updated'))
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    photoSaving.value = false
  }
}

onMounted(load)
</script>
