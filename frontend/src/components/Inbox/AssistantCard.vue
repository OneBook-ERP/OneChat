<template>
  <div class="flex flex-col gap-2 rounded-4 border border-outline-gray-2 bg-surface-base p-3">
    <div class="flex items-start justify-between gap-3">
      <div class="min-w-0">
        <p class="truncate text-xs text-ink-gray-5">{{ card.doctype_label }} · {{ card.name }}</p>
        <TruncatedText class="block truncate text-sm font-medium text-ink-gray-9" :text="card.title" />
        <p v-if="card.subtitle || card.date" class="truncate text-xs text-ink-gray-5">
          {{ [card.subtitle, card.date].filter(Boolean).join(' · ') }}
        </p>
      </div>
      <div class="flex shrink-0 flex-col items-end gap-1">
        <Badge v-if="card.status" size="sm" variant="subtle" :theme="card.theme" :label="card.status" />
        <p v-if="card.amount" class="text-sm font-semibold tabular-nums text-ink-gray-9">{{ card.amount.value }}</p>
        <p v-if="card.due" class="text-xs font-medium tabular-nums text-ink-red-6">
          {{ __('Due {0}').format(card.due.value) }}
        </p>
      </div>
    </div>

    <dl v-if="card.fields?.length" class="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-xs">
      <template v-for="field in card.fields" :key="field.label">
        <dt class="text-ink-gray-5">{{ field.label }}</dt>
        <dd class="min-w-0 truncate text-ink-gray-8">{{ field.value }}</dd>
      </template>
    </dl>

    <div class="flex flex-wrap gap-1.5">
      <Button
        v-if="card.pay && contact"
        size="sm"
        variant="solid"
        icon-left="lucide-credit-card"
        :label="__('Send payment link')"
        :loading="sending"
        :disabled="disabled"
        @click="sendLink"
      />
      <Button size="sm" variant="subtle" icon-left="lucide-arrow-up-right" :label="__('Open')" @click="open" />
      <Button
        size="sm"
        variant="ghost"
        icon-left="lucide-message-circle-question"
        :label="__('Ask about this')"
        :disabled="disabled"
        @click="emit('ask', __('Tell me more about {0} {1}').format(card.doctype_label, card.name))"
      />
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { Badge, Button, toast } from 'frappe-ui'
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { runRowAction } from '@/data/integrations'
import { useUI } from '@/stores/ui'
import { errorMessage } from '@/utils/format'
import { translate as __ } from '@/translation'

const props = defineProps({
  card: { type: Object, required: true },
  contact: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
})

const emit = defineEmits(['ask'])

const router = useRouter()
const ui = useUI()
const sending = ref(false)

function open() {
  if (props.card.open?.route) router.push(props.card.open.route)
  else if (props.card.open?.url) window.open(props.card.open.url, '_blank', 'noopener')
}

function sendLink() {
  ui.confirm({
    title: __('Send a payment link?'),
    message: __('{0} {1} gets a payment link in this chat for {2}.').format(
      props.card.doctype_label,
      props.card.name,
      props.card.due?.value || props.card.amount?.value || '',
    ),
    action: __('Send link'),
    onConfirm: async () => {
      sending.value = true
      try {
        await runRowAction(props.contact, 'erpnext', { key: 'payment_link' }, { doctype: props.card.doctype, name: props.card.name })
        toast.success(__('Payment link sent'))
      } catch (err) {
        toast.error(errorMessage(err))
      } finally {
        sending.value = false
      }
    },
  })
}
</script>
