<template>
  <div class="mt-1.5 flex items-center gap-1.5 rounded-3 bg-surface-alpha-gray-2 py-1 pl-2 pr-0.5 text-sm" @click.stop>
    <span class="font-medium tabular-nums text-ink-gray-9">{{ payment.amount_label }}</span>
    <Badge
      size="sm"
      variant="subtle"
      :theme="STATUS[payment.status]?.theme || 'gray'"
      :label="__(STATUS[payment.status]?.label || payment.status)"
    />
    <TruncatedText class="min-w-0 flex-1 truncate text-xs text-ink-gray-5" :text="detail" />
    <Dropdown v-if="menu.length" :options="menu" placement="right">
      <Button size="sm" variant="ghost" icon="lucide-ellipsis" :tooltip="__('Payment actions')" :loading="busy" />
    </Dropdown>
  </div>

  <ResponsiveDialog v-model:open="dialog.open" :title="dialog.mode === 'refund' ? __('Refund payment') : __('Mark as paid')" size="sm">
    <template #default>
      <div class="flex flex-col gap-3">
        <template v-if="dialog.mode === 'refund'">
          <FormControl
            v-model="dialog.amount"
            type="number"
            :label="__('Amount')"
            :description="__('Up to {0}. Leave as is for a full refund.').format(left)"
          />
          <TabButtons
            v-model="dialog.speed"
            class="self-start"
            :options="[
              { label: __('Normal'), value: 'normal' },
              { label: __('Instant'), value: 'instant' },
            ]"
          />
          <p class="text-sm text-ink-gray-5">{{ __('Reverse the Payment Entry in ERPNext once the refund goes through.') }}</p>
        </template>
        <FormControl
          v-else
          v-model="dialog.reference"
          type="text"
          :label="__('UPI reference (UTR)')"
          :description="__('Check your bank app for the payment before confirming.')"
        />
        <ErrorMessage :message="dialog.error" />
      </div>
    </template>
    <template #actions>
      <div class="flex justify-end gap-2">
        <Button variant="subtle" :label="__('Cancel')" @click="dialog.open = false" />
        <Button
          variant="solid"
          :theme="dialog.mode === 'refund' ? 'red' : 'gray'"
          :label="dialog.mode === 'refund' ? __('Refund') : __('Mark as paid')"
          :loading="busy"
          @click="submit"
        />
      </div>
    </template>
  </ResponsiveDialog>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { Badge, Button, Dropdown, ErrorMessage, FormControl, TabButtons, call, toast } from 'frappe-ui'
import ResponsiveDialog from '@/components/Common/ResponsiveDialog.vue'
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { can, session } from '@/data/session'
import { errorMessage } from '@/utils/format'
import { translate as __ } from '@/translation'

const props = defineProps({ payment: { type: Object, required: true } })

const STATUS = {
  Pending: { label: 'Awaiting payment', theme: 'amber' },
  Paid: { label: 'Paid', theme: 'green' },
  Failed: { label: 'Failed', theme: 'red' },
  Refunded: { label: 'Refunded', theme: 'gray' },
  'Partly Refunded': { label: 'Partly refunded', theme: 'blue' },
  Canceled: { label: 'Cancelled', theme: 'gray' },
}
const ORDER = {
  processing: 'Processing',
  partially_shipped: 'Partly shipped',
  shipped: 'Shipped',
  completed: 'Completed',
  canceled: 'Canceled',
}
const MOVE = {
  processing: { label: 'Mark as processing', icon: 'lucide-package' },
  partially_shipped: { label: 'Mark as partly shipped', icon: 'lucide-package-open' },
  shipped: { label: 'Mark as shipped', icon: 'lucide-truck' },
  completed: { label: 'Mark as completed', icon: 'lucide-circle-check' },
  canceled: { label: 'Cancel order', icon: 'lucide-circle-x' },
}

const busy = ref(false)
const dialog = reactive({ open: false, mode: 'paid', amount: '', speed: 'normal', reference: '', error: '' })

const upi = computed(() => props.payment.provider === 'upi_vpa')
const paid = computed(() => ['Paid', 'Partly Refunded'].includes(props.payment.status))
const left = computed(() => (props.payment.amount - (props.payment.refunded || 0)).toFixed(2))

const detail = computed(() =>
  [
    props.payment.reference_name,
    ORDER[props.payment.order_status] && __(ORDER[props.payment.order_status]),
    props.payment.method && props.payment.method.toUpperCase(),
    props.payment.error,
  ]
    .filter(Boolean)
    .join(' · '),
)

const menu = computed(() => {
  const items = []
  if (props.payment.status === 'Canceled') return items
  if (!upi.value && !paid.value && props.payment.status !== 'Refunded') {
    items.push({ label: __('Check payment status'), icon: 'lucide-refresh-cw', onClick: () => act('refresh') })
  }
  if (!can('OneChat WhatsApp Payment', 'write')) return items
  if (upi.value && ['Pending', 'Failed'].includes(props.payment.status)) {
    items.push({ label: __('Mark as paid'), icon: 'lucide-badge-check', onClick: () => openDialog('paid') })
  }
  for (const status of props.payment.next || []) {
    if (status !== 'canceled' && !paid.value) continue
    items.push({ label: __(MOVE[status].label), icon: MOVE[status].icon, onClick: () => act('update_status', { status }) })
  }
  if (session.user.is_admin && paid.value && !upi.value) {
    items.push({ label: __('Refund'), icon: 'lucide-undo-2', onClick: () => openDialog('refund') })
  }
  return items
})

function openDialog(mode) {
  Object.assign(dialog, { open: true, mode, amount: left.value, speed: 'normal', reference: '', error: '' })
}

async function act(method, args = {}) {
  busy.value = true
  try {
    await call(`onechat.whatsapp.pay.${method}`, { name: props.payment.name, ...args })
    return true
  } catch (err) {
    const message = errorMessage(err)
    if (dialog.open) dialog.error = message
    else toast.error(message)
    return false
  } finally {
    busy.value = false
  }
}

async function submit() {
  dialog.error = ''
  const done =
    dialog.mode === 'refund'
      ? await act('refund', { amount: Number(dialog.amount) || undefined, speed: dialog.speed })
      : await act('mark_paid', { reference: dialog.reference.trim() })
  if (!done) return
  dialog.open = false
  toast.success(dialog.mode === 'refund' ? __('Refund started') : __('Marked as paid'))
}
</script>
