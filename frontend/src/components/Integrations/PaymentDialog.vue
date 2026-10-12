<template>
  <ResponsiveDialog v-model:open="open" :title="__('Request payment')" size="lg">
    <template #default>
      <div class="flex flex-col gap-4">
        <div v-if="loading" class="flex flex-col gap-2">
          <Skeleton v-for="row in 3" :key="row" class="h-14 w-full" />
        </div>

        <template v-else>
          <div v-if="state.whatsapp" class="flex flex-col gap-1.5">
            <TabButtons
              v-model="method"
              class="self-start"
              :options="[
                { label: __('In WhatsApp'), value: 'whatsapp', iconLeft: 'lucide-wallet' },
                { label: __('Payment link'), value: 'link', iconLeft: 'lucide-link' },
              ]"
            />
            <p class="text-sm text-ink-gray-5">
              {{
                method === 'whatsapp'
                  ? __('The customer reviews the order and pays without leaving the chat.')
                  : __('Sends a link to your ERPNext payment gateway.')
              }}
            </p>
          </div>

          <p v-if="blocked" class="flex items-start gap-1.5 text-sm text-ink-amber-8">
            <span class="lucide-triangle-alert mt-0.5 size-4 shrink-0" aria-hidden="true" />
            {{ blocked }}
          </p>
          <p v-else-if="method === 'link' && !state.window && state.template" class="flex items-center gap-1.5 text-sm text-ink-gray-5">
            <span class="lucide-layout-template size-4 shrink-0" aria-hidden="true" />
            {{ __('The chat is closed, so the link goes out as your payment template.') }}
          </p>
          <p v-else-if="method === 'link' && !state.window" class="flex items-start gap-1.5 text-sm text-ink-gray-6">
            <span class="lucide-info mt-0.5 size-4 shrink-0" aria-hidden="true" />
            {{
              __(
                'The chat is closed and no payment template is set, so it goes out as a normal message. WhatsApp may hold it until the customer writes back.',
              )
            }}
          </p>

          <p v-if="replacing" class="flex items-start gap-1.5 text-sm text-ink-gray-6">
            <span class="lucide-refresh-ccw mt-0.5 size-4 shrink-0" aria-hidden="true" />
            {{ replacing }}
          </p>

          <p v-if="!state.documents.length" class="text-sm text-ink-gray-5">
            {{ __('Nothing is due. This customer has no unpaid invoices or open orders.') }}
          </p>

          <div v-else class="flex flex-col gap-1.5">
            <FormLabel :label="__('Collect for')" />
            <ScrollArea class="rounded-4 border border-outline-gray-2" viewport-class="max-h-64">
              <div class="flex flex-col p-1">
                <button
                  v-for="row in state.documents"
                  :key="`${row.doctype}-${row.name}`"
                  type="button"
                  class="flex items-center gap-3 rounded-3 px-2.5 py-2 text-left transition-colors hover:bg-surface-gray-1"
                  :class="{ 'bg-surface-gray-2': isPicked(row) }"
                  @click="pick(row)"
                >
                  <span
                    :class="isPicked(row) ? 'lucide-circle-dot text-ink-gray-9' : 'lucide-circle text-ink-gray-4'"
                    class="size-4 shrink-0"
                    aria-hidden="true"
                  />
                  <span class="min-w-0 flex-1">
                    <span class="flex items-center gap-1.5">
                      <TruncatedText class="truncate text-sm font-medium text-ink-gray-9" :text="row.name" />
                      <Badge size="sm" variant="subtle" :theme="row.doctype === 'Sales Invoice' ? 'blue' : 'violet'">
                        {{ row.doctype === 'Sales Invoice' ? __('Invoice') : __('Order') }}
                      </Badge>
                    </span>
                    <TruncatedText
                      class="block truncate text-xs text-ink-gray-5"
                      :text="
                        [manyCustomers && row.customer, row.date, row.hint, __('Total {0}').format(row.total)].filter(Boolean).join(' · ')
                      "
                    />
                  </span>
                  <span class="shrink-0 text-right">
                    <span class="block text-sm font-medium tabular-nums text-ink-gray-9">{{ row.due_label }}</span>
                    <span class="block text-xs text-ink-gray-5">{{ __('due') }}</span>
                  </span>
                </button>
              </div>
            </ScrollArea>
          </div>

          <template v-if="picked">
            <div class="flex flex-col gap-1.5">
              <FormLabel :label="__('Amount')" />
              <TabButtons
                v-model="mode"
                class="self-start"
                :options="[
                  { label: __('Full balance ({0})').format(picked.due_label), value: 'full' },
                  { label: picked.doctype === 'Sales Order' ? __('Advance or part') : __('Part payment'), value: 'part' },
                ]"
              />
              <FormControl
                v-if="mode === 'part'"
                v-model="amount"
                type="number"
                :placeholder="__('Amount in {0}').format(picked.currency)"
                :description="__('Up to {0}.').format(picked.due_label)"
              />
            </div>
            <FormControl
              v-model="message"
              type="textarea"
              :rows="2"
              :label="__('Message (optional)')"
              :placeholder="__('Hi, here is your payment request for {0}.').format(picked.name)"
              :description="
                method === 'whatsapp' ? __('Shown above the Review and pay button.') : __('Shown above the amount and the Pay button.')
              "
            />

            <div v-if="showPreview" class="flex flex-col gap-1.5">
              <FormLabel :label="__('What the customer sees')" />
              <div class="rounded-5 bg-surface-gray-2 p-3">
                <div class="ml-auto w-full max-w-72 overflow-hidden rounded-5 rounded-tr-1 bg-surface-green-2 shadow-sm">
                  <div class="flex flex-col gap-2 px-3 pb-2 pt-2.5 text-sm leading-5 text-ink-gray-9">
                    <p v-if="method === 'link'" class="font-semibold">{{ __('Payment request') }}</p>
                    <p class="whitespace-pre-wrap break-words">{{ previewText }}</p>
                    <div class="flex flex-col gap-0.5 rounded-3 bg-surface-alpha-gray-2 px-2.5 py-2">
                      <p class="flex justify-between gap-3">
                        <span class="text-ink-gray-6">{{ __('Amount') }}</span>
                        <span class="font-semibold tabular-nums">{{ previewAmount }}</span>
                      </p>
                      <p class="flex justify-between gap-3">
                        <span class="text-ink-gray-6">{{ __('For') }}</span>
                        <span class="truncate">{{ __(picked.doctype) }} {{ picked.name }}</span>
                      </p>
                    </div>
                    <p v-if="method === 'link'" class="text-xs text-ink-gray-5">{{ __('Secure payment link') }}</p>
                  </div>
                  <div
                    class="flex items-center justify-center gap-1.5 border-t border-outline-gray-2 py-2 text-sm font-medium text-ink-blue-6"
                  >
                    <span
                      :class="method === 'whatsapp' ? 'lucide-shopping-cart' : 'lucide-external-link'"
                      class="size-3.5"
                      aria-hidden="true"
                    />
                    {{ method === 'whatsapp' ? __('Review and pay') : __('Pay {0}').format(previewAmount) }}
                  </div>
                </div>
              </div>
            </div>
          </template>

          <ErrorMessage :message="error" />
        </template>
      </div>
    </template>

    <template #actions>
      <div class="flex justify-end gap-2">
        <Button variant="subtle" :label="__('Cancel')" @click="open = false" />
        <Button
          variant="solid"
          icon-left="lucide-send"
          :label="method === 'whatsapp' ? __('Send payment request') : __('Send payment link')"
          :disabled="!canSend"
          :loading="sending"
          @click="send"
        />
      </div>
    </template>
  </ResponsiveDialog>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { computed, reactive, ref, watch } from 'vue'
import { Badge, Button, ErrorMessage, FormControl, FormLabel, ScrollArea, Skeleton, TabButtons, call } from 'frappe-ui'
import ResponsiveDialog from '@/components/Common/ResponsiveDialog.vue'
import { runAction } from '@/data/integrations'
import { errorMessage } from '@/utils/format'
import { translate as __ } from '@/translation'

const props = defineProps({
  contact: { type: String, required: true },
  action: { type: Object, required: true },
})

const emit = defineEmits(['done'])
const open = defineModel('open', { type: Boolean, default: false })

const state = reactive({ documents: [], gateway: true, window: true, template: false, whatsapp: false })
const method = ref('link')
const picked = ref(null)
const mode = ref('full')
const amount = ref('')
const message = ref('')
const loading = ref(false)
const sending = ref(false)
const error = ref('')

const partAmount = computed(() => Number(amount.value) || 0)
const blocked = computed(() => {
  if (method.value === 'whatsapp') {
    if (!state.window)
      return __('This customer hasn’t written in 24 hours, so WhatsApp won’t deliver a payment request. Send a payment link instead.')
    if (picked.value && picked.value.currency && picked.value.currency !== 'INR') return __('WhatsApp payments only support INR.')
    return ''
  }
  if (!state.gateway) return __('No default payment gateway in ERPNext yet. Add one in Payment Gateway Account.')
  return ''
})

const replacing = computed(() => {
  const open = picked.value?.open
  if (!open) return ''
  const links = open.links || []
  const whatsapp = open.whatsapp || []
  if (method.value === 'whatsapp') {
    if (links.length) return __('Sending cancels the open payment link {0}, so the customer can only pay once.').format(links.join(', '))
    if (whatsapp.length) return __('Sending withdraws the earlier WhatsApp payment request for this document.')
    return ''
  }
  if (whatsapp.length)
    return __('Sending withdraws the open WhatsApp payment request for this document, so the customer can only pay once.')
  if (links.length)
    return __('The open payment link {0} is reused if the amount is the same. Otherwise it is cancelled.').format(links.join(', '))
  return ''
})

const manyCustomers = computed(() => new Set(state.documents.map((row) => row.customer).filter(Boolean)).size > 1)
const showPreview = computed(() => !!picked.value && !blocked.value && (method.value === 'whatsapp' || state.window || !state.template))
const previewAmount = computed(() => {
  if (!picked.value) return ''
  if (mode.value === 'part' && partAmount.value > 0) {
    return new Intl.NumberFormat(undefined, { style: 'currency', currency: picked.value.currency || 'INR' }).format(partAmount.value)
  }
  return picked.value.due_label
})
const previewText = computed(() => {
  const typed = message.value.trim()
  if (typed) return typed
  if (method.value === 'whatsapp') return __('Hi, please review and pay for {0}.').format(picked.value?.name || '')
  return __('Hi, here is your payment request for {0} {1}.').format(__(picked.value?.doctype || ''), picked.value?.name || '')
})

const canSend = computed(() => {
  if (!picked.value || blocked.value) return false
  if (mode.value === 'part') return partAmount.value > 0 && partAmount.value <= picked.value.due + 0.01
  return true
})

function isPicked(row) {
  return picked.value?.doctype === row.doctype && picked.value?.name === row.name
}

function pick(row) {
  picked.value = row
  mode.value = 'full'
  amount.value = ''
  error.value = ''
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    Object.assign(state, await call('onechat.integrations.payments.payable_documents', { contact: props.contact }))
    method.value = state.whatsapp && state.window ? 'whatsapp' : 'link'
    picked.value = state.documents[0] || null
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    loading.value = false
  }
}

async function send() {
  sending.value = true
  error.value = ''
  try {
    const result = await runAction(props.contact, props.action, {
      doctype: picked.value.doctype,
      name: picked.value.name,
      amount: mode.value === 'part' ? partAmount.value : undefined,
      message: message.value.trim(),
      method: method.value,
    })
    emit('done', result)
    open.value = false
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    sending.value = false
  }
}

watch(
  open,
  (value) => {
    if (!value) return
    picked.value = null
    mode.value = 'full'
    amount.value = ''
    message.value = ''
    load()
  },
  { immediate: true },
)
</script>
