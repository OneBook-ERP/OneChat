<template>
  <div :id="`message-${message.name}`" class="group flex" :class="[mine ? 'justify-end' : 'justify-start', first ? 'mt-2' : 'mt-0.5']">
    <div class="flex min-w-0 max-w-[85%] items-center gap-1 sm:max-w-[70%]" :class="mine ? 'flex-row-reverse' : 'flex-row'">
      <div class="flex min-w-0 flex-col" :class="mine ? 'items-end' : 'items-start'">
        <div
          class="relative min-w-0 max-w-full rounded-5 px-2 pb-1.5 pt-1.5 shadow-sm"
          :class="[
            mine ? 'bg-surface-green-2' : 'bg-surface-gray-2',
            highlighted && 'ring-2 ring-outline-amber-3 transition-shadow',
            first && (mine ? 'rounded-tr-1' : 'rounded-tl-1'),
            message.pending && message.status === 'pending' && 'opacity-80',
            touch && 'select-none [-webkit-touch-callout:none]',
          ]"
          @click.capture="onClickCapture"
          @click="onTap"
          @contextmenu="onContextMenu"
          @touchstart.passive="onTouchStart"
          @touchmove.passive="onTouchMove"
          @touchend="cancelPress"
          @touchcancel="cancelPress"
        >
          <p v-if="template" class="mb-1 flex items-center gap-1 px-0.5 text-xs font-medium text-ink-gray-5">
            <span class="lucide-layout-template size-3.5" aria-hidden="true" />
            {{ __('Template') }}
            <span v-if="message.template_name" class="truncate font-normal">· {{ message.template_name }}</span>
          </p>

          <ReplyPreview v-if="message.reply" :message="message.reply" :contact-name="contactName" class="mb-1" />

          <button
            v-if="media.kind === 'image'"
            type="button"
            class="block overflow-hidden rounded-4"
            :aria-label="__('Open photo')"
            @click.stop="emit('open', media.url)"
          >
            <img :src="media.url" alt="" loading="lazy" class="max-h-60 w-64 max-w-full object-cover" />
          </button>

          <video
            v-else-if="media.kind === 'video'"
            :src="media.url"
            controls
            preload="metadata"
            class="max-h-60 w-64 max-w-full rounded-4 bg-surface-gray-9"
          />

          <audio v-else-if="kind === 'audio' && message.attach" :src="message.attach" controls class="w-64 max-w-full" />

          <a
            v-else-if="media.kind === 'document'"
            :href="media.url"
            target="_blank"
            rel="noopener"
            download
            class="flex w-64 max-w-full items-center gap-2.5 rounded-4 bg-surface-alpha-gray-2 p-2.5 hover:bg-surface-alpha-gray-3"
            @click.stop
          >
            <span class="lucide-file-text size-6 shrink-0 text-ink-gray-6" aria-hidden="true" />
            <span class="min-w-0 flex-1">
              <TruncatedText class="block truncate text-sm font-medium text-ink-gray-8" :text="fileName(media.url)" />
              <span class="block text-xs uppercase text-ink-gray-5">{{ extension }}</span>
            </span>
            <span class="lucide-download size-4 shrink-0 text-ink-gray-5" aria-hidden="true" />
          </a>

          <component
            :is="message.link_url ? 'a' : 'div'"
            v-else-if="instagramCard"
            :href="message.link_url || undefined"
            :target="message.link_url ? '_blank' : undefined"
            :rel="message.link_url ? 'noopener noreferrer' : undefined"
            class="flex w-64 max-w-full items-center gap-2.5 rounded-4 bg-surface-alpha-gray-2 p-2.5"
            :class="{ 'hover:bg-surface-alpha-gray-3': message.link_url }"
            @click.stop
          >
            <ChannelIcon channel="Instagram" class="size-5 shrink-0 text-ink-gray-6" />
            <span class="min-w-0 flex-1 text-sm font-medium text-ink-gray-8">{{ instagramCard }}</span>
            <span v-if="message.link_url" class="lucide-external-link size-4 shrink-0 text-ink-gray-5" aria-hidden="true" />
          </component>

          <a
            v-else-if="location"
            :href="location.url"
            target="_blank"
            rel="noopener"
            class="flex items-start gap-2.5 rounded-4 bg-surface-gray-2 px-2.5 py-2 transition-colors hover:bg-surface-gray-3"
          >
            <span class="lucide-map-pin mt-0.5 size-4 shrink-0 text-ink-gray-6" aria-hidden="true" />
            <span class="flex min-w-0 flex-col gap-0.5">
              <span class="truncate text-sm font-medium text-ink-gray-9">{{ location.title }}</span>
              <span class="truncate text-xs text-ink-gray-6">{{ location.subtitle }}</span>
              <span class="text-xs text-ink-blue-6">{{ __('Open in Maps') }}</span>
            </span>
          </a>

          <div v-else-if="order" class="flex w-72 max-w-full flex-col gap-2 px-0.5 pt-0.5">
            <div class="flex items-center gap-2">
              <span
                class="grid size-8 shrink-0 place-content-center rounded-full bg-surface-alpha-gray-2 text-ink-gray-7"
                aria-hidden="true"
              >
                <span class="lucide-shopping-cart size-4" />
              </span>
              <div class="min-w-0">
                <p class="text-sm font-semibold text-ink-gray-9">{{ __('New order') }}</p>
                <p class="text-xs text-ink-gray-5">
                  {{ order.count === '1' ? __('1 item') : __('{0} items').format(order.count) }}
                </p>
              </div>
            </div>
            <ul class="flex flex-col divide-y divide-outline-gray-2 overflow-hidden rounded-4 bg-surface-alpha-gray-2">
              <li v-for="item in order.items" :key="item.code" class="flex items-center gap-2.5 p-2">
                <img
                  v-if="item.image"
                  :src="item.image"
                  alt=""
                  loading="lazy"
                  class="size-10 shrink-0 rounded-3 bg-surface-gray-3 object-cover"
                />
                <span v-else class="grid size-10 shrink-0 place-content-center rounded-3 bg-surface-gray-3" aria-hidden="true">
                  <span class="lucide-package size-4 text-ink-gray-5" />
                </span>
                <span class="min-w-0 flex-1">
                  <TruncatedText class="block truncate text-sm font-medium text-ink-gray-9" :text="item.name" />
                  <span class="block truncate text-xs tabular-nums text-ink-gray-5">
                    {{ [item.name !== item.code && item.code, `${item.qty} × ${item.price}`].filter(Boolean).join(' · ') }}
                  </span>
                </span>
                <span class="shrink-0 text-sm font-medium tabular-nums text-ink-gray-8">{{ item.amount }}</span>
              </li>
            </ul>
            <div class="flex items-center justify-between px-0.5">
              <span class="text-sm text-ink-gray-6">{{ __('Total') }}</span>
              <span class="text-base font-semibold tabular-nums text-ink-gray-9">{{ order.total }}</span>
            </div>
            <p v-if="order.note" class="rounded-3 bg-surface-alpha-gray-2 px-2 py-1.5 text-sm text-ink-gray-7">
              <span class="lucide-message-square-text mr-1 inline-block size-3.5 align-[-2px] text-ink-gray-5" aria-hidden="true" />
              {{ order.note }}
            </p>
            <ol v-if="order.journey?.length" class="flex flex-col border-t border-outline-gray-2 pt-1.5">
              <li v-for="(step, index) in order.journey" :key="step.key" class="relative">
                <span
                  v-if="index < order.journey.length - 1"
                  class="absolute left-[0.6875rem] top-6 h-[calc(100%-1.25rem)] w-px"
                  :class="step.state === 'done' ? 'bg-surface-green-6' : 'bg-outline-gray-2'"
                  aria-hidden="true"
                />
                <component
                  :is="step.url ? 'a' : 'div'"
                  :href="step.url || undefined"
                  :target="step.url ? '_blank' : undefined"
                  :rel="step.url ? 'noopener' : undefined"
                  class="flex items-center gap-2 rounded-3 px-0.5 py-1 text-xs"
                  :class="step.url && 'hover:bg-surface-alpha-gray-2'"
                  @click.stop
                >
                  <span class="grid size-5 shrink-0 place-content-center" aria-hidden="true">
                    <span :class="STEPS[step.state]?.icon || STEPS.todo.icon" class="size-4" />
                  </span>
                  <span class="shrink-0 font-medium" :class="step.state === 'todo' ? 'text-ink-gray-5' : 'text-ink-gray-8'">
                    {{ step.label }}
                  </span>
                  <span class="ml-auto min-w-0 truncate text-right text-ink-gray-5">{{ step.detail }}</span>
                  <span v-if="step.url" class="lucide-arrow-up-right size-3 shrink-0 text-ink-gray-4" aria-hidden="true" />
                </component>
              </li>
            </ol>
          </div>

          <div v-else-if="catalog" class="flex w-72 max-w-full flex-col gap-2 px-0.5 pt-0.5">
            <div class="flex items-center gap-2">
              <span
                class="grid size-8 shrink-0 place-content-center rounded-full bg-surface-alpha-gray-2 text-ink-gray-7"
                aria-hidden="true"
              >
                <span class="lucide-shopping-bag size-4" />
              </span>
              <div class="min-w-0">
                <TruncatedText class="block truncate text-sm font-semibold text-ink-gray-9" :text="catalog.header || __('Products')" />
                <p class="text-xs text-ink-gray-5">
                  {{ catalog.items.length === 1 ? __('1 product') : __('{0} products').format(catalog.items.length) }}
                </p>
              </div>
            </div>
            <p v-if="catalog.body" class="whitespace-pre-line px-0.5 text-sm text-ink-gray-8">{{ catalog.body }}</p>
            <ul class="flex flex-col divide-y divide-outline-gray-2 overflow-hidden rounded-4 bg-surface-alpha-gray-2">
              <li v-for="item in catalog.items" :key="item.code" class="flex items-center gap-2.5 p-2">
                <img
                  v-if="item.image"
                  :src="item.image"
                  alt=""
                  loading="lazy"
                  class="size-10 shrink-0 rounded-3 bg-surface-gray-3 object-cover"
                />
                <span v-else class="grid size-10 shrink-0 place-content-center rounded-3 bg-surface-gray-3" aria-hidden="true">
                  <span class="lucide-package size-4 text-ink-gray-5" />
                </span>
                <span class="min-w-0 flex-1">
                  <TruncatedText class="block truncate text-sm font-medium text-ink-gray-9" :text="item.name" />
                  <span v-if="item.name !== item.code" class="block truncate text-xs text-ink-gray-5">{{ item.code }}</span>
                </span>
                <span v-if="item.price" class="shrink-0 text-sm font-medium tabular-nums text-ink-gray-8">{{ item.price }}</span>
              </li>
            </ul>
          </div>

          <p v-else-if="placeholder" class="flex items-center gap-1.5 px-0.5 py-1 text-sm italic text-ink-gray-6">
            <span :class="placeholder.icon" class="size-4" aria-hidden="true" />
            {{ placeholder.label }}
          </p>

          <CommentActions v-if="kind === 'comment'" :message="message" />

          <p v-if="template && message.template_header" class="px-0.5 pt-1 text-base font-semibold text-ink-gray-9">
            {{ message.template_header }}
          </p>
          <p v-else-if="cta?.header" class="px-0.5 pt-1 text-base font-semibold text-ink-gray-9">{{ cta.header }}</p>

          <div v-if="body" class="relative px-0.5" :class="{ 'pt-1': media.kind || hasMedia || placeholder }">
            <span
              class="whitespace-pre-wrap break-words text-base leading-relaxed text-ink-gray-9 [overflow-wrap:anywhere]"
              v-html="body"
            />
            <template v-if="inlineMeta">
              <span class="inline-block h-3" :class="mine ? 'w-[4.5rem]' : 'w-14'" aria-hidden="true" />
              <span class="absolute bottom-0 right-0.5 inline-flex items-center gap-1 text-xs tabular-nums text-ink-gray-5">
                <span v-if="accountLabel" class="max-w-24 truncate" :title="accountLabel">{{ accountLabel }} ·</span>
                {{ clock(message.creation) }}
                <MessageStatus v-if="mine" :tick="tick" :error="deliveryError" />
              </span>
            </template>
          </div>

          <PaymentChip v-if="message.payment" :payment="message.payment" />

          <p v-if="cta?.footer" class="px-0.5 pt-1 text-xs text-ink-gray-5">{{ cta.footer }}</p>
          <a
            v-if="cta?.url && !linkClosed"
            :href="cta.url"
            target="_blank"
            rel="noopener"
            class="-mx-2 mt-1.5 flex items-center justify-center gap-1.5 border-t border-outline-gray-2 px-2 pt-1.5 text-sm font-medium text-ink-blue-6 hover:underline"
            @click.stop
          >
            <span class="lucide-external-link size-3.5" aria-hidden="true" />
            {{ cta.button }}
          </a>
          <p
            v-else-if="cta?.url"
            class="-mx-2 mt-1.5 flex items-center justify-center gap-1.5 border-t border-outline-gray-2 px-2 pt-1.5 text-sm font-medium text-ink-gray-4 line-through"
          >
            <span class="lucide-external-link size-3.5" aria-hidden="true" />
            {{ cta.button }}
          </p>
          <div v-if="message.payment_link" class="mt-1 flex items-center gap-1.5 px-0.5 text-xs" @click.stop>
            <TruncatedText class="min-w-0 truncate text-ink-gray-5" :text="message.payment_link.request" />
            <Badge size="sm" variant="subtle" :theme="linkLook.theme" :label="linkLook.label" />
            <Dropdown v-if="linkMenu.length" :options="linkMenu" placement="right">
              <Button class="ml-auto" size="sm" variant="ghost" icon="lucide-ellipsis" :tooltip="__('Payment actions')" />
            </Dropdown>
          </div>

          <p v-if="template && message.template_footer" class="px-0.5 pt-1 text-xs text-ink-gray-5">
            {{ message.template_footer }}
          </p>

          <div v-if="!inlineMeta" class="flex items-center justify-end gap-1 px-0.5 pt-1 text-xs tabular-nums text-ink-gray-5">
            <span v-if="accountLabel" class="max-w-24 truncate" :title="accountLabel">{{ accountLabel }} ·</span>
            {{ clock(message.creation) }}
            <MessageStatus v-if="mine" :tick="tick" :error="deliveryError" />
          </div>
        </div>

        <div v-if="message.reactions?.length" class="relative z-[1] -mt-1.5 flex gap-0.5 px-2">
          <span
            v-for="emoji in message.reactions"
            :key="emoji"
            class="rounded-full border border-outline-gray-1 bg-surface-elevation-2 px-1.5 py-px text-sm shadow-sm"
          >
            {{ emoji }}
          </span>
        </div>

        <div v-if="message.pending && message.status === 'failed'" class="mt-1 flex items-center gap-2 text-xs text-ink-red-7">
          <span class="lucide-circle-alert size-3.5" aria-hidden="true" />
          <TruncatedText class="truncate" :text="message.error || __('Not sent')" />
          <button type="button" class="font-medium underline underline-offset-2" @click="emit('retry')">
            {{ __('Retry') }}
          </button>
          <button type="button" class="text-ink-gray-5 hover:text-ink-gray-7" @click="emit('discard')">
            {{ __('Discard') }}
          </button>
        </div>
      </div>

      <div
        v-if="!message.pending && !touch"
        class="flex shrink-0 items-center transition-opacity focus-within:opacity-100 group-hover:opacity-100"
        :class="selected || picker ? 'opacity-100' : 'opacity-0'"
      >
        <Button variant="ghost" size="sm" icon="lucide-reply" :tooltip="__('Reply')" :label="__('Reply')" @click="emit('reply')" />

        <Popover v-model:open="picker" side="top" align="center">
          <template #trigger>
            <Button variant="ghost" size="sm" icon="lucide-smile-plus" :label="__('React')" />
          </template>
          <template #default>
            <div class="flex gap-0.5 p-1">
              <button
                v-for="emoji in REACTIONS"
                :key="emoji"
                type="button"
                class="grid size-8 place-content-center rounded-4 text-lg transition-transform hover:scale-110 hover:bg-surface-gray-2"
                :class="{ 'bg-surface-gray-3': message.reactions?.includes(emoji) }"
                @click="pick(emoji)"
              >
                {{ emoji }}
              </button>
            </div>
          </template>
        </Popover>

        <Button
          v-if="copyText"
          variant="ghost"
          size="sm"
          icon="lucide-copy"
          :tooltip="__('Copy text')"
          :label="__('Copy text')"
          @click="copyMessage(message)"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import ChannelIcon from '@/components/Common/ChannelIcon.vue'
import CommentActions from './CommentActions.vue'
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { computed, onBeforeUnmount, ref } from 'vue'
import { Badge, Button, Dropdown, Popover, call, toast } from 'frappe-ui'
import MessageStatus from './MessageStatus.vue'
import ReplyPreview from './ReplyPreview.vue'
import PaymentChip from './PaymentChip.vue'
import { REACTIONS, contentLabel, copyMessage, fileName, messageBody, plainMessage, richText } from '@/data/inbox'
import { useUI } from '@/stores/ui'
import { useNumbers } from '@/stores/numbers'
import { session } from '@/data/session'
import { clock, errorMessage } from '@/utils/format'
import { translate as __ } from '@/translation'

const ICONS = {
  image: 'lucide-image',
  video: 'lucide-video',
  audio: 'lucide-mic',
  document: 'lucide-file-text',
  location: 'lucide-map-pin',
  contact: 'lucide-contact',
  flow: 'lucide-clipboard-list',
  interactive: 'lucide-list',
  button: 'lucide-mouse-pointer-click',
  product: 'lucide-shopping-bag',
  product_list: 'lucide-shopping-bag',
  order: 'lucide-shopping-cart',
  order_details: 'lucide-wallet',
  order_status: 'lucide-package',
}

const STEPS = {
  done: { icon: 'lucide-circle-check text-ink-green-6' },
  partial: { icon: 'lucide-circle-dot text-ink-amber-6' },
  failed: { icon: 'lucide-circle-x text-ink-red-6' },
  todo: { icon: 'lucide-circle text-ink-gray-4' },
}

const TICKS = {
  pending: { icon: 'lucide-clock', class: 'text-ink-gray-5', label: 'Sending' },
  failed: { icon: 'lucide-circle-alert', class: 'text-ink-red-7', label: 'Not delivered' },
  read: { icon: 'lucide-check-check', class: 'text-ink-blue-5', label: 'Read' },
  delivered: { icon: 'lucide-check-check', class: 'text-ink-gray-5', label: 'Delivered' },
  sent: { icon: 'lucide-check', class: 'text-ink-gray-5', label: 'Sent' },
}

const props = defineProps({
  message: { type: Object, required: true },
  contactName: { type: String, default: '' },
  first: { type: Boolean, default: true },
  selected: { type: Boolean, default: false },
  highlighted: { type: Boolean, default: false },
  touch: { type: Boolean, default: false },
})

const emit = defineEmits(['reply', 'react', 'retry', 'discard', 'open', 'select', 'actions'])

const picker = ref(false)

const mine = computed(() => props.message.type === 'Outgoing')

const numbers = useNumbers()
const accountLabel = computed(() => {
  const shown = numbers.rows.filter((row) => row.shown)
  if (shown.length < 2 || !props.message.whatsapp_account) return ''
  const row = numbers.rows.find((item) => item.name === props.message.whatsapp_account)
  return row?.label || props.message.whatsapp_account
})
const template = computed(() => props.message.message_type === 'Template')
const kind = computed(() => props.message.content_type || 'text')
const INSTAGRAM_CARDS = {
  story_reply: 'Replied to your story',
  story_mention: 'Mentioned you in their story',
  share: 'Shared a post',
  comment: 'Commented on your post',
  comment_reply: 'Replied publicly to a comment',
}
const instagramCard = computed(() => (INSTAGRAM_CARDS[kind.value] ? __(INSTAGRAM_CARDS[kind.value]) : ''))
const hasMedia = computed(() => ['image', 'video', 'audio', 'document'].includes(kind.value) && !!props.message.attach)
const media = computed(() => {
  if (template.value && props.message.template_media) return { kind: props.message.template_media_type, url: props.message.template_media }
  if (hasMedia.value && kind.value !== 'audio') return { kind: kind.value, url: props.message.attach }
  return { kind: '', url: '' }
})

const location = computed(() => {
  if (kind.value !== 'location') return null
  const lat = Number(props.message.latitude)
  const lng = Number(props.message.longitude)
  if (!lat && !lng) return null
  const [title, ...rest] = String(props.message.message || '')
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
  return {
    title: title || __('Shared location'),
    subtitle: rest.join(', ') || `${lat.toFixed(5)}, ${lng.toFixed(5)}`,
    url: `https://www.google.com/maps?q=${lat},${lng}`,
  }
})

const text = computed(() => messageBody(props.message))

const order = computed(() => (kind.value === 'order' && props.message.order?.items?.length ? props.message.order : null))

const catalog = computed(() =>
  ['product', 'product_list'].includes(kind.value) && props.message.catalog?.items?.length ? props.message.catalog : null,
)

const body = computed(() => (location.value || order.value || catalog.value || !plainMessage(text.value) ? '' : richText(text.value)))
const copyText = computed(() => plainMessage(text.value))
const inlineMeta = computed(() => !!body.value && !(template.value && props.message.template_footer) && !cta.value)

const cta = computed(() => {
  if (kind.value !== 'interactive' || !props.message.buttons) return null
  try {
    const spec = typeof props.message.buttons === 'string' ? JSON.parse(props.message.buttons) : props.message.buttons
    return spec?.type === 'cta_url' ? spec : null
  } catch {
    return null
  }
})

const LINK_LOOK = {
  Paid: { label: 'Paid', theme: 'green' },
  Cancelled: { label: 'Cancelled', theme: 'gray' },
  Failed: { label: 'Failed', theme: 'red' },
  'Partially Paid': { label: 'Part paid', theme: 'blue' },
}
const linkLook = computed(() => {
  const look = LINK_LOOK[props.message.payment_link?.status]
  return look ? { label: __(look.label), theme: look.theme } : { label: __('Open'), theme: 'amber' }
})
const linkClosed = computed(() => ['Paid', 'Cancelled', 'Failed'].includes(props.message.payment_link?.status))
const linkMenu = computed(() => {
  if (linkClosed.value || !props.message.payment_link) return []
  const items = []
  if (session.user.is_admin) items.push({ label: __('Mark as paid'), icon: 'lucide-badge-check', onClick: () => markLink('Paid') })
  items.push({ label: __('Mark as failed'), icon: 'lucide-circle-x', onClick: () => markLink('Failed') })
  items.push({ label: __('Cancel request'), icon: 'lucide-ban', onClick: cancelLink })
  return items
})

function markLink(status) {
  const request = props.message.payment_link.request
  ui.confirm({
    title: status === 'Paid' ? __('Mark as paid?') : __('Mark as failed?'),
    message:
      status === 'Paid'
        ? __('A Payment Entry is created in ERPNext for {0}. Use this only when the money has reached you.').format(request)
        : __('{0} is marked as failed and its link stops showing here. The customer is not told automatically.').format(request),
    action: status === 'Paid' ? __('Mark as paid') : __('Mark as failed'),
    theme: status === 'Paid' ? 'gray' : 'red',
    onConfirm: async () => {
      try {
        toast.success(await call('onechat.integrations.payments.mark_link', { message: props.message.name, status }))
      } catch (err) {
        toast.error(errorMessage(err))
      }
    },
  })
}

const ui = useUI()

function cancelLink() {
  ui.confirm({
    title: __('Cancel payment request?'),
    message: __('{0} is cancelled in ERPNext and its link stops working. The customer is not told automatically.').format(
      props.message.payment_link.request,
    ),
    action: __('Cancel request'),
    theme: 'red',
    onConfirm: async () => {
      try {
        toast.success(await call('onechat.integrations.payments.cancel_link', { message: props.message.name }))
      } catch (err) {
        toast.error(errorMessage(err))
      }
    },
  })
}

const placeholder = computed(() => {
  if (kind.value === 'text' || hasMedia.value || cta.value || location.value || order.value || catalog.value) return null
  if (
    ['location', 'contact', 'flow', 'interactive', 'button', 'product', 'product_list', 'order', 'order_details', 'order_status'].includes(
      kind.value,
    ) &&
    body.value
  ) {
    return { icon: ICONS[kind.value], label: contentLabel(kind.value) || __('Button reply') }
  }
  if (body.value) return null

  return { icon: ICONS[kind.value] || 'lucide-paperclip', label: contentLabel(kind.value) || __('Attachment') }
})

const extension = computed(() => {
  const name = fileName(media.value.url || props.message.attach)
  return name.includes('.') ? name.split('.').pop() : __('File')
})

const failed = computed(() => String(props.message.status || '').toLowerCase() === 'failed')

const tick = computed(() => {
  const status = String(props.message.status || 'sent').toLowerCase()
  const entry = TICKS[status] || TICKS.sent
  return { ...entry, label: __(entry.label) }
})

const deliveryError = computed(() => (!props.message.pending && failed.value && props.message.error_message) || '')

function pick(emoji) {
  picker.value = false
  emit('react', emoji)
}

let pressTimer = null
let pressed = false
let origin = null

function openActions() {
  pressed = true
  cancelPress()
  navigator.vibrate?.(10)
  emit('actions')
}

function onTouchStart(event) {
  pressed = false
  if (!props.touch || props.message.pending) return

  const point = event.touches[0]
  origin = { x: point.clientX, y: point.clientY }
  clearTimeout(pressTimer)
  pressTimer = setTimeout(openActions, 500)
}

function onTouchMove(event) {
  const point = event.touches[0]
  if (origin && Math.hypot(point.clientX - origin.x, point.clientY - origin.y) > 10) cancelPress()
}

function cancelPress() {
  clearTimeout(pressTimer)
  pressTimer = null
  origin = null
}

function onContextMenu(event) {
  if (!props.touch) return

  event.preventDefault()
  if (!pressed && !props.message.pending) openActions()
}

function onClickCapture(event) {
  if (!pressed) return

  event.preventDefault()
  event.stopPropagation()
  pressed = false
}

function onTap() {
  if (!props.touch) emit('select')
}

onBeforeUnmount(cancelPress)
</script>
