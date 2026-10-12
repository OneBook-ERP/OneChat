<template>
  <div class="flex flex-col gap-3">
    <div class="flex items-center justify-between gap-2">
      <div class="flex items-center gap-1">
        <p class="text-sm font-medium text-ink-gray-5">{{ __('Payment configurations') }}</p>
        <InfoHint
          :title="__('WhatsApp payments')"
          :text="
            __(
              'Customers review the order and pay inside WhatsApp by UPI, card or net banking. A configuration links your payment gateway account to this WhatsApp Business Account. Payment requests use the one marked In use.',
            )
          "
        />
      </div>
      <div class="flex items-center gap-1">
        <Button variant="ghost" icon="lucide-rotate-cw" :tooltip="__('Refresh')" :loading="loading" @click="load" />
        <Button v-if="!state.unavailable" size="sm" icon-left="lucide-plus" :label="__('New')" @click="openCreate" />
      </div>
    </div>

    <ErrorMessage :message="error" />

    <div v-if="loading && !loaded" class="flex flex-col gap-2">
      <Skeleton v-for="row in 2" :key="row" class="h-12 w-full" />
    </div>

    <section v-else-if="state.unavailable" class="flex flex-col gap-3 rounded-4 border border-outline-gray-2 p-4">
      <div class="flex items-start gap-3">
        <span class="grid size-8 shrink-0 place-content-center rounded-full bg-surface-amber-2 text-ink-amber-8" aria-hidden="true">
          <span :class="UNAVAILABLE[state.unavailable.kind].icon" class="size-4" />
        </span>
        <div class="min-w-0">
          <p class="text-sm font-semibold text-ink-gray-9">{{ __(UNAVAILABLE[state.unavailable.kind].title) }}</p>
          <p class="mt-0.5 text-sm text-ink-gray-6">{{ __(UNAVAILABLE[state.unavailable.kind].text) }}</p>
        </div>
      </div>
      <ol class="ml-11 list-decimal space-y-1 pl-4 text-sm text-ink-gray-7">
        <li v-for="step in UNAVAILABLE[state.unavailable.kind].steps" :key="step">{{ __(step) }}</li>
      </ol>
      <div class="ml-11 flex flex-wrap items-center gap-2">
        <Button size="sm" variant="solid" icon-left="lucide-rotate-cw" :label="__('Check again')" :loading="loading" @click="load" />
        <Button
          size="sm"
          icon-right="lucide-arrow-up-right"
          :label="__('Open WhatsApp Manager')"
          link="https://business.facebook.com/wa/manage/home/"
        />
      </div>
      <Tooltip :text="state.unavailable.detail">
        <p class="ml-11 truncate text-xs text-ink-gray-5">{{ __('Meta: {0}').format(state.unavailable.detail) }}</p>
      </Tooltip>
    </section>

    <p v-else-if="!state.configurations.length" class="flex items-center gap-2 text-sm text-ink-gray-5">
      <span class="lucide-wallet size-4 shrink-0" aria-hidden="true" />
      {{ __('No payment configuration yet. Create one and connect your Razorpay, PayU or Zaakpay account, or use your UPI ID.') }}
    </p>

    <div v-else class="divide-y divide-outline-gray-1 rounded-4 border border-outline-gray-2">
      <div v-for="row in state.configurations" :key="row.name" class="flex items-center gap-3 px-3 py-2">
        <span
          :class="row.name === state.selected ? 'lucide-circle-dot text-ink-gray-9' : 'lucide-circle text-ink-gray-4'"
          class="size-4 shrink-0"
          aria-hidden="true"
        />
        <div class="min-w-0 flex-1">
          <div class="flex items-center gap-1.5">
            <TruncatedText class="truncate text-sm font-medium text-ink-gray-9" :text="row.name" />
            <Badge v-if="row.name === state.selected" size="sm" variant="subtle" theme="gray" :label="__('In use')" />
          </div>
          <TruncatedText
            class="block truncate text-xs text-ink-gray-5"
            :text="[PROVIDERS[row.provider] || row.provider, row.vpa].filter(Boolean).join(' · ')"
          />
        </div>
        <Badge
          size="sm"
          variant="subtle"
          :theme="STATUS[row.status]?.theme || 'gray'"
          :label="__(STATUS[row.status]?.label || row.status || 'Unknown')"
        />
        <Button
          v-if="needsConnect(row)"
          size="sm"
          variant="solid"
          :label="__('Connect')"
          :loading="busy === row.name"
          @click="connect(row)"
        />
        <Button v-else-if="row.name !== state.selected" size="sm" :label="__('Use')" :loading="busy === row.name" @click="use(row)" />
        <Dropdown :options="menu(row)" placement="right">
          <Button size="sm" variant="ghost" icon="lucide-ellipsis" :tooltip="__('More')" />
        </Dropdown>
      </div>
    </div>

    <ResponsiveDialog v-model:open="creating" :title="__('New payment configuration')" size="md">
      <template #default>
        <div class="flex flex-col gap-3">
          <FormControl
            v-model="form.name"
            type="text"
            :label="__('Name')"
            placeholder="shop-payments"
            :description="__('Letters, digits, dashes or underscores.')"
          />
          <FormControl v-model="form.provider" type="select" :label="__('Provider')" :options="providerOptions" />
          <FormControl
            v-if="form.provider === 'upi_vpa'"
            v-model="form.vpa"
            type="text"
            :label="__('UPI ID')"
            placeholder="shop@okhdfc"
            :description="__('Payments go straight to this UPI ID. Agents confirm them with the UTR from your bank app.')"
          />
          <div class="grid grid-cols-2 gap-3">
            <FormControl v-model="form.mcc" type="text" :label="__('Merchant category code')" placeholder="5712" />
            <FormControl v-model="form.purpose_code" type="text" :label="__('Purpose code')" placeholder="00" />
          </div>
          <p v-if="form.provider !== 'upi_vpa'" class="text-sm text-ink-gray-5">
            {{ __('After creating, sign in to {0} in the new tab to link your account.').format(PROVIDERS[form.provider]) }}
          </p>
          <ErrorMessage :message="createError" />
        </div>
      </template>
      <template #actions>
        <div class="flex justify-end gap-2">
          <Button variant="subtle" :label="__('Cancel')" @click="creating = false" />
          <Button variant="solid" :label="__('Create')" :loading="saving" :disabled="!form.name.trim()" @click="create" />
        </div>
      </template>
    </ResponsiveDialog>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { Badge, Button, Dropdown, ErrorMessage, FormControl, Skeleton, Tooltip, call, toast } from 'frappe-ui'
import InfoHint from '@/components/Common/InfoHint.vue'
import ResponsiveDialog from '@/components/Common/ResponsiveDialog.vue'
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { useSocket } from '@/data/socket'
import { useUI } from '@/stores/ui'
import { errorMessage } from '@/utils/format'
import { translate as __ } from '@/translation'

const props = defineProps({ account: { type: String, required: true } })
const emit = defineEmits(['changed'])
const ui = useUI()

const PROVIDERS = { razorpay: 'Razorpay', payu: 'PayU', zaakpay: 'Zaakpay', upi_vpa: 'UPI ID' }
const STATUS = {
  Active: { label: 'Active', theme: 'green' },
  Needs_Connecting: { label: 'Not connected', theme: 'amber' },
  Needs_Testing: { label: 'Needs testing', theme: 'blue' },
}
const providerOptions = Object.entries(PROVIDERS).map(([value, label]) => ({ label, value }))

const state = reactive({ configurations: [], selected: '', active: false, unavailable: null })

const UNAVAILABLE = {
  not_enabled: {
    icon: 'lucide-wallet',
    title: 'WhatsApp payments aren’t enabled for this account',
    text: 'Meta only turns on payments for eligible Indian businesses. Until then it can’t list or create payment configurations.',
    steps: [
      'In WhatsApp Manager, open Account tools and look for Payment configurations.',
      'If it isn’t there, check the business is verified, registered in India and billed in INR, then ask Meta support or your BSP to enable payments.',
      'Once you can see it, come back and check again. Payment links from ERPNext keep working meanwhile.',
    ],
  },
  permission: {
    icon: 'lucide-key-round',
    title: 'The access token can’t manage payments',
    text: 'Meta refused the request for this token.',
    steps: [
      'In Meta Business Settings, generate a new token for the system user with whatsapp_business_management and whatsapp_business_messaging.',
      'Paste it on the Setup tab and save, then check again.',
    ],
  },
  token: {
    icon: 'lucide-key-round',
    title: 'The access token was rejected',
    text: 'It has expired or was revoked in Meta.',
    steps: ['Generate a new token in Meta Business Settings.', 'Paste it on the Setup tab and save, then check again.'],
  },
}
const loading = ref(false)
const loaded = ref(false)
const error = ref('')
const busy = ref('')
const creating = ref(false)
const saving = ref(false)
const createError = ref('')
const form = reactive({ name: '', provider: 'razorpay', vpa: '', mcc: '', purpose_code: '' })

function needsConnect(row) {
  return row.provider !== 'upi_vpa' && row.status === 'Needs_Connecting'
}

function update(value) {
  Object.assign(state, { unavailable: null }, value)
  emit('changed', { configuration: state.selected, active: state.active })
}

async function run(key, method, args) {
  busy.value = key
  error.value = ''
  try {
    return await call(`onechat.whatsapp.pay.${method}`, { account: props.account, ...args })
  } catch (err) {
    error.value = errorMessage(err)
    return null
  } finally {
    busy.value = ''
  }
}

async function load() {
  loading.value = true
  const value = await run('', 'configurations', {})
  if (value) update(value)
  loading.value = false
  loaded.value = true
}

async function use(row) {
  const value = await run(row.name, 'use_configuration', { name: row.name })
  if (value) {
    update(value)
    toast.success(__('{0} is now used for payment requests').format(row.name))
  }
}

async function connect(row) {
  const url = await run(row.name, 'connect_link', { name: row.name })
  if (url) {
    window.open(url, '_blank', 'noopener')
    toast.info(__('Finish signing in to {0} in the new tab, then refresh.').format(PROVIDERS[row.provider] || row.provider))
  }
}

function remove(row) {
  ui.confirm({
    title: __('Remove {0}?').format(row.name),
    message: __('Payment requests already sent with it can no longer be paid.'),
    action: __('Remove'),
    theme: 'red',
    onConfirm: async () => {
      const value = await run(row.name, 'remove_configuration', { name: row.name })
      if (value) update(value)
    },
  })
}

function menu(row) {
  return [
    {
      label: __('Use for payment requests'),
      icon: 'lucide-circle-dot',
      onClick: () => use(row),
      condition: () => row.name !== state.selected,
    },
    {
      label: row.status === 'Active' ? __('Reconnect') : __('Connect'),
      icon: 'lucide-link',
      onClick: () => connect(row),
      condition: () => row.provider !== 'upi_vpa',
    },
    { label: __('Remove'), icon: 'lucide-trash-2', theme: 'red', onClick: () => remove(row) },
  ]
}

function openCreate() {
  Object.assign(form, { name: '', provider: 'razorpay', vpa: '', mcc: '', purpose_code: '' })
  createError.value = ''
  creating.value = true
}

async function create() {
  saving.value = true
  createError.value = ''
  try {
    const value = await call('onechat.whatsapp.pay.create_configuration', { account: props.account, ...form, name: form.name.trim() })
    update(value)
    creating.value = false
    if (value.oauth_url) {
      window.open(value.oauth_url, '_blank', 'noopener')
      toast.info(__('Sign in to {0} in the new tab to finish connecting.').format(PROVIDERS[form.provider]))
    } else {
      toast.success(__('Payment configuration created'))
    }
  } catch (err) {
    createError.value = errorMessage(err)
  } finally {
    saving.value = false
  }
}

watch(() => props.account, load)
onMounted(() => {
  load()
  useSocket().on('onechat_pay_configuration', load)
})
onBeforeUnmount(() => useSocket().off('onechat_pay_configuration', load))
</script>
