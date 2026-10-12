<template>
  <ResponsiveDialog v-model:open="open" :title="__('Follow up')" size="md">
    <template #default>
      <p class="mb-3 text-sm text-ink-gray-6">
        {{ __('Creates a new draft broadcast for the people you pick. Nothing is sent until you press Send now.') }}
      </p>
      <ErrorMessage :message="error" class="mb-2" />

      <div v-if="loading" class="flex flex-col gap-2">
        <Skeleton v-for="row in 3" :key="row" class="h-14 w-full" />
      </div>
      <div v-else class="flex flex-col gap-2">
        <button
          v-for="option in OPTIONS"
          :key="option.value"
          type="button"
          class="flex items-center gap-3 rounded-5 border px-3 py-2.5 text-left transition-colors"
          :class="audience === option.value ? 'border-outline-gray-5 bg-surface-gray-2' : 'border-outline-gray-2 hover:bg-surface-gray-1'"
          :disabled="!counts[option.value]"
          @click="audience = option.value"
        >
          <span :class="option.icon" class="size-4 shrink-0 text-ink-gray-6" aria-hidden="true" />
          <span class="min-w-0 flex-1">
            <span class="block text-base font-medium text-ink-gray-8">{{ __(option.label) }}</span>
            <span class="block text-sm text-ink-gray-5">{{ __(option.description) }}</span>
          </span>
          <span class="shrink-0 text-base tabular-nums" :class="counts[option.value] ? 'text-ink-gray-8' : 'text-ink-gray-4'">
            {{ formatNumber(counts[option.value] || 0) }}
          </span>
        </button>

        <LinkField
          v-model="template"
          class="mt-2"
          doctype="WhatsApp Templates"
          :label="__('Template')"
          :filters="account ? { whatsapp_account: account } : {}"
          :description="__('Keep the same template, or pick a different one for the follow-up.')"
        />
      </div>
    </template>

    <template #actions>
      <Button
        variant="solid"
        class="w-full"
        size="lg"
        icon-left="lucide-copy-plus"
        :loading="creating"
        :disabled="!audience || !counts[audience]"
        :label="audience ? __('Create draft for {0}').format(formatNumber(counts[audience] || 0)) : __('Create draft')"
        @click="create"
      />
    </template>
  </ResponsiveDialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { Button, ErrorMessage, Skeleton, call, toast } from 'frappe-ui'
import LinkField from '@/components/Common/LinkField.vue'
import ResponsiveDialog from '@/components/Common/ResponsiveDialog.vue'
import { errorMessage, formatNumber } from '@/utils/format'
import { translate as __ } from '@/translation'

const props = defineProps({
  name: { type: String, default: null },
  template: { type: String, default: '' },
  account: { type: String, default: '' },
})

const emit = defineEmits(['created'])
const open = defineModel('open', { type: Boolean, default: false })

const OPTIONS = [
  {
    value: 'read_no_reply',
    label: 'Read it, didn’t reply',
    description: 'Interested enough to open it. Often the best group to nudge.',
    icon: 'lucide-eye',
  },
  { value: 'not_read', label: 'Didn’t read it', description: 'Delivered but never opened.', icon: 'lucide-eye-off' },
  {
    value: 'no_reply',
    label: 'Everyone who didn’t reply',
    description: 'Everyone it was sent to who hasn’t replied yet.',
    icon: 'lucide-users',
  },
]

const counts = ref({})
const loading = ref(false)
const creating = ref(false)
const error = ref('')
const audience = ref('')
const template = ref('')

async function load() {
  loading.value = true
  error.value = ''
  audience.value = ''
  template.value = props.template || ''
  try {
    counts.value = await call('onechat.campaigns.broadcasts.follow_up_counts', { name: props.name })
    audience.value = OPTIONS.find((option) => counts.value[option.value])?.value || ''
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    loading.value = false
  }
}

async function create() {
  creating.value = true
  error.value = ''
  try {
    const name = await call('onechat.campaigns.broadcasts.create_follow_up', {
      name: props.name,
      audience: audience.value,
      template: template.value || null,
    })
    toast.success(__('Follow-up draft created'))
    open.value = false
    emit('created', name)
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    creating.value = false
  }
}

watch(open, (value) => value && props.name && load())
</script>
