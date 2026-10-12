<template>
  <template v-if="!dialog">
    <SettingsHeader :title="__('Payments')" :description="__('Send payment links for invoices and orders from chats and flows')">
      <template #actions>
        <Button variant="solid" :loading="saving" :disabled="loading" :label="__('Save')" @click="save" />
      </template>
    </SettingsHeader>
  </template>

  <component :is="dialog ? 'div' : SettingsBody">
    <div v-if="loading" class="flex flex-col gap-3 pt-4">
      <Skeleton v-for="row in 4" :key="row" class="h-12 w-full" />
    </div>

    <div v-else class="flex flex-col gap-6 pt-4">
      <ErrorMessage :message="error" />

      <div class="flex flex-col gap-2">
        <div class="flex items-center justify-between gap-3">
          <p class="text-base font-medium text-ink-gray-8">{{ __('Payment gateway') }}</p>
          <Tooltip v-if="form.ready" :text="__('Payment links are created with your default gateway in ERPNext.')">
            <span
              class="inline-flex cursor-default items-center gap-1 rounded-full bg-surface-green-1 px-2 py-0.5 text-xs text-ink-green-7"
            >
              <span class="lucide-circle-check size-3 shrink-0" aria-hidden="true" />
              {{ __('Ready') }}
            </span>
          </Tooltip>
        </div>
        <div v-if="form.ready" class="flex flex-wrap gap-1.5">
          <span
            v-for="row in form.gateways"
            :key="row.name"
            class="inline-flex max-w-full items-center gap-1 rounded-full border border-outline-gray-2 px-2 py-0.5 text-xs text-ink-gray-7"
          >
            <span v-if="row.is_default" class="lucide-star size-3 shrink-0 text-ink-amber-6" :aria-label="__('Default')" />
            <TruncatedText class="truncate" :text="[row.payment_gateway, row.company, row.currency].filter(Boolean).join(' · ')" />
          </span>
        </div>
        <div v-else class="flex flex-col gap-2 rounded-4 bg-surface-amber-1 p-3 text-sm text-ink-amber-8">
          <p class="flex items-center gap-2 font-medium">
            <span class="lucide-triangle-alert size-4 shrink-0" aria-hidden="true" />
            {{ __('No default payment gateway in ERPNext yet') }}
          </p>
          <ol class="list-decimal space-y-1 pl-5 text-ink-gray-7">
            <li>{{ __('Open Razorpay Settings (or Stripe, PayPal…) in ERPNext and enter your API key and secret.') }}</li>
            <li>
              {{
                __(
                  'Create a Payment Gateway Account: pick the gateway, your company, currency and the account payments go into, and tick Default.',
                )
              }}
            </li>
            <li>{{ __('In your gateway’s dashboard, add your site as the webhook so payments are confirmed automatically.') }}</li>
          </ol>
        </div>
      </div>

      <div class="flex flex-col gap-3">
        <div>
          <p class="text-base font-medium text-ink-gray-8">{{ __('When the chat is closed') }}</p>
          <p class="mt-0.5 text-sm text-ink-gray-5">
            {{ __('WhatsApp only allows templates if the customer hasn’t written in 24 hours. Pick approved templates for those cases.') }}
          </p>
        </div>
        <LinkField
          v-model="form.payment_template"
          doctype="WhatsApp Templates"
          :label="__('Payment link template')"
          :description="__('Its values are filled in this order: 1 first name, 2 amount, 3 invoice or order, 4 payment link.')"
        />
        <div class="divide-y divide-outline-gray-1">
          <SettingsRow
            :title="__('Sales team can send from Desk')"
            :description="
              __(
                'Adds Send payment link on WhatsApp to submitted Sales Orders and Sales Invoices. Anyone who can create Payment Requests can use it, even without OneChat access. Messages show in the customer’s chat.',
              )
            "
          >
            <Switch v-model="form.desk_payment_links" />
          </SettingsRow>
          <SettingsRow
            :title="__('Send a receipt when paid')"
            :description="__('Thanks the customer on WhatsApp as soon as the gateway confirms the payment.')"
          >
            <Switch v-model="form.payment_receipts" />
          </SettingsRow>
        </div>
        <LinkField
          v-if="form.payment_receipts"
          v-model="form.receipt_template"
          doctype="WhatsApp Templates"
          :label="__('Receipt template')"
          :description="
            __(
              'Values: 1 first name, 2 amount, 3 invoice or order, 4 date, 5 payment mode. Without it, receipts only go out while the chat is open.',
            )
          "
        />
      </div>

      <p class="flex items-start gap-1.5 text-sm text-ink-gray-5">
        <span class="lucide-wallet mt-0.5 size-4 shrink-0" aria-hidden="true" />
        {{ __('To let customers pay inside WhatsApp (India, INR), open Settings → WhatsApp, pick the number and use its Payments tab.') }}
      </p>
    </div>
    <div v-if="dialog && !loading" class="flex justify-end gap-2 pt-5">
      <Button variant="solid" :loading="saving" :label="__('Save')" @click="save" />
    </div>
  </component>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { Button, ErrorMessage, SettingsBody, SettingsHeader, SettingsRow, Skeleton, Switch, Tooltip, call, toast } from 'frappe-ui'
import TruncatedText from '@/components/Common/TruncatedText.vue'
import LinkField from '@/components/Common/LinkField.vue'
import { integrations } from '@/data/integrations'
import { errorMessage } from '@/utils/format'
import { translate as __ } from '@/translation'

defineProps({ dialog: { type: Boolean, default: false } })
const emit = defineEmits(['saved'])

const loading = ref(true)
const saving = ref(false)
const error = ref('')
const form = reactive({
  payment_template: '',
  receipt_template: '',
  payment_receipts: true,
  desk_payment_links: true,
  gateways: [],
  ready: false,
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    Object.assign(form, await call('onechat.integrations.payments.get_settings'))
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
    Object.assign(
      form,
      await call('onechat.integrations.payments.save_settings', {
        payment_template: form.payment_template || null,
        receipt_template: form.receipt_template || null,
        payment_receipts: form.payment_receipts ? 1 : 0,
        desk_payment_links: form.desk_payment_links ? 1 : 0,
      }),
    )
    integrations.reload()
    toast.success(__('Payment settings saved'))
    emit('saved')
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>
