<template>
  <SettingsHeader>
    <div class="flex items-start justify-between gap-3">
      <div class="min-w-0">
        <h2 class="text-lg font-semibold text-ink-gray-8">{{ __('App') }}</h2>
        <p class="mt-1 text-base text-ink-gray-6">
          {{ __('How OneChat looks when your team installs it on a phone or computer') }}
        </p>
      </div>
      <Button variant="solid" :label="__('Save')" :loading="saving" :disabled="loading || !dirty" @click="save" />
    </div>
  </SettingsHeader>

  <SettingsBody>
    <ErrorMessage :message="error" class="pt-4" />

    <div v-if="loading" class="flex flex-col gap-3 pt-6">
      <Skeleton v-for="row in 4" :key="row" class="h-12 w-full" />
    </div>

    <div v-else class="grid gap-8 pt-6 md:grid-cols-[minmax(0,1fr)_200px]">
      <div class="flex min-w-0 flex-col gap-5">
        <div class="grid gap-4 sm:grid-cols-2">
          <FormControl v-model="form.app_name" type="text" :label="__('App name')" :placeholder="'OneChat'" />
          <FormControl
            v-model="form.app_short_name"
            type="text"
            :label="__('Short name')"
            :placeholder="'OneChat'"
            :maxlength="12"
            :description="__('Shown under the icon. Up to 12 characters.')"
          />
        </div>

        <div class="flex flex-col gap-2">
          <FormLabel :label="__('Icon')" />
          <div class="flex flex-wrap items-center gap-3">
            <img :src="iconPreview" alt="" class="size-14 rounded-5 border border-outline-gray-1 object-cover" />
            <FileUploader
              file-types="image/png,image/jpeg,image/webp"
              :private="false"
              :validate-file="checkFile"
              @success="(file) => (form.app_icon = file.file_url)"
            >
              <template #default="{ openFileSelector, uploading, progress }">
                <Button
                  variant="subtle"
                  icon-left="lucide-upload"
                  :loading="uploading"
                  :label="uploading ? `${progress}%` : form.app_icon ? __('Replace') : __('Upload icon')"
                  @click="openFileSelector"
                />
              </template>
            </FileUploader>
            <Button v-if="form.app_icon" variant="ghost" :label="__('Use the OneChat icon')" @click="form.app_icon = null" />
          </div>
          <p class="text-sm text-ink-gray-5">
            {{ __('A square PNG, at least 512 × 512. OneChat makes every size phones and computers need.') }}
          </p>
        </div>

        <div class="flex flex-col gap-2">
          <FormLabel :label="__('Theme colour')" />
          <div class="flex flex-wrap items-center gap-2">
            <button
              v-for="color in SWATCHES"
              :key="color"
              type="button"
              class="size-7 rounded-full ring-offset-2 ring-offset-surface-base transition-shadow"
              :class="form.app_theme_color?.toLowerCase() === color ? 'ring-2 ring-outline-gray-5' : ''"
              :style="{ background: color }"
              :aria-label="color"
              @click="form.app_theme_color = color"
            />
            <FormControl type="text" v-model="form.app_theme_color" class="w-28 font-mono" placeholder="#1f8a5b" />
          </div>
          <p class="text-sm text-ink-gray-5">{{ __('Used for the splash screen and as the background of the adaptive icon.') }}</p>
        </div>

        <div class="divide-y divide-outline-gray-1 border-t border-outline-gray-1">
          <SettingsRow
            :title="__('Show the Install app button')"
            :description="__('Adds Install app to everyone\'s account menu when their browser supports it')"
          >
            <Switch v-model="installButton" />
          </SettingsRow>
          <SettingsRow :title="__('Install on this device')" :description="installHint">
            <Button
              variant="subtle"
              icon-left="lucide-download"
              :disabled="install.installed"
              :label="install.installed ? __('Installed') : __('Install app')"
              @click="installNow"
            />
          </SettingsRow>
        </div>
      </div>

      <aside class="flex flex-col items-center gap-3">
        <p class="self-start text-sm text-ink-gray-5">{{ __('Preview') }}</p>
        <div class="flex w-full flex-col items-center gap-2 rounded-7 bg-surface-gray-2 px-4 py-6">
          <img :src="iconPreview" alt="" class="size-16 rounded-6 object-cover shadow-sm" />
          <TruncatedText class="max-w-full truncate text-sm text-ink-gray-8" :text="form.app_short_name || form.app_name || 'OneChat'" />
        </div>
        <div class="flex w-full flex-col items-center justify-center gap-2 rounded-7 py-6" :style="{ background: validColor }">
          <img :src="iconPreview" alt="" class="size-12 rounded-5 object-cover" />
          <span class="text-sm font-medium text-white">{{ form.app_name || 'OneChat' }}</span>
        </div>
        <p class="text-center text-xs text-ink-gray-5">{{ __('Home screen and splash screen') }}</p>
      </aside>
    </div>
  </SettingsBody>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { computed, onMounted, reactive, ref } from 'vue'
import {
  Button,
  ErrorMessage,
  FileUploader,
  FormControl,
  FormLabel,
  SettingsBody,
  SettingsHeader,
  SettingsRow,
  Skeleton,
  Switch,
  call,
  toast,
} from 'frappe-ui'
import { install, promptInstall, saveAppSettings } from '@/data/install'
import { errorMessage } from '@/utils/format'
import { translate as __ } from '@/translation'

const SWATCHES = ['#1f8a5b', '#128c7e', '#2563eb', '#7c3aed', '#db2777', '#ea580c', '#171717']
const DEFAULT_ICON = '/assets/onechat/frontend/icons/icon-512.png'
const FIELDS = ['app_name', 'app_short_name', 'app_icon', 'app_theme_color', 'app_install_button']

const loading = ref(true)
const saving = ref(false)
const error = ref('')
const saved = ref({})
const form = reactive({ app_name: '', app_short_name: '', app_icon: null, app_theme_color: '#1f8a5b', app_install_button: 1 })

const installButton = computed({
  get: () => Boolean(form.app_install_button),
  set: (value) => (form.app_install_button = value ? 1 : 0),
})
const dirty = computed(() => FIELDS.some((key) => (form[key] ?? null) !== (saved.value[key] ?? null)))
const iconPreview = computed(() => form.app_icon || DEFAULT_ICON)
const validColor = computed(() => (/^#[0-9a-fA-F]{6}$/.test(form.app_theme_color || '') ? form.app_theme_color : '#1f8a5b'))
const installHint = computed(() => {
  if (install.installed) return __('OneChat is already running as an installed app here.')
  if (install.prompt) return __('Your browser is ready to install OneChat.')
  if (install.ios) return __('On iPhone and iPad, tap Share and then Add to Home Screen.')
  return __('If nothing happens, use the install icon in the address bar or the browser menu.')
})

function pick(values) {
  return Object.fromEntries(FIELDS.map((key) => [key, values[key] ?? null]))
}

function checkFile(file) {
  if (!/^image\/(png|jpeg|webp)$/.test(file.type)) return __('Upload a PNG, JPG or WebP image')
  return null
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const values = pick(await call('onechat.pwa.settings'))
    saved.value = values
    Object.assign(form, values)
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  error.value = ''
  try {
    const values = pick(await saveAppSettings({ ...form }))
    saved.value = values
    Object.assign(form, values)
    toast.success(__('Saved. Installed apps pick this up the next time they open.'))
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    saving.value = false
  }
}

async function installNow() {
  const outcome = await promptInstall()
  if (outcome === 'manual') toast(__('Install OneChat'), { description: installHint.value, duration: 10000 })
}

onMounted(load)
</script>
