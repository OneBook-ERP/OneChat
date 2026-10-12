<template>
  <div class="rounded-5 border border-outline-gray-1" data-tour="account-guide">
    <button
      type="button"
      class="flex w-full items-center gap-3 px-4 py-3 text-left"
      :aria-expanded="expanded"
      @click="expanded = !expanded"
    >
      <span
        class="grid size-8 shrink-0 place-content-center rounded-full"
        :class="complete ? 'bg-surface-green-2 text-ink-green-3' : 'bg-surface-gray-2 text-ink-gray-6'"
      >
        <span :class="complete ? 'lucide-circle-check' : 'lucide-list-checks'" class="size-4" aria-hidden="true" />
      </span>
      <div class="min-w-0 flex-1">
        <p class="text-base font-medium text-ink-gray-8">
          {{ complete ? __('Setup complete') : instagram ? __('Connect this Instagram account') : __('Connect this number to Meta') }}
        </p>
        <p class="text-sm text-ink-gray-5">
          {{
            complete
              ? __('All {0} steps done').format(steps.length)
              : __('Step {0} of {1}: {2}').format(currentIndex + 1, steps.length, __(steps[currentIndex].title))
          }}
        </p>
      </div>
      <div class="hidden h-1.5 w-24 overflow-hidden rounded-full bg-surface-gray-2 sm:block" aria-hidden="true">
        <div class="h-full rounded-full bg-surface-green-6 transition-all" :style="{ width: `${(doneCount / steps.length) * 100}%` }" />
      </div>
      <span :class="expanded ? 'lucide-chevron-up' : 'lucide-chevron-down'" class="size-4 shrink-0 text-ink-gray-5" aria-hidden="true" />
    </button>

    <ol v-if="expanded" class="flex flex-col gap-1 border-t border-outline-gray-1 p-2">
      <li
        v-for="(step, index) in steps"
        :key="step.key"
        class="flex gap-3 rounded-4 px-2 py-2"
        :class="index === currentIndex ? 'bg-surface-gray-1 ring-1 ring-outline-gray-2' : ''"
        :aria-current="index === currentIndex ? 'step' : undefined"
      >
        <span
          class="mt-0.5 grid size-5 shrink-0 place-content-center rounded-full text-xs font-medium"
          :class="
            step.done
              ? 'bg-surface-green-6 text-ink-white'
              : index === currentIndex
                ? 'bg-surface-gray-7 text-ink-white'
                : 'border border-outline-gray-3 text-ink-gray-4'
          "
        >
          <span v-if="step.done" class="lucide-check size-3" aria-hidden="true" />
          <template v-else>{{ index + 1 }}</template>
        </span>

        <div class="min-w-0 flex-1">
          <p
            class="text-base"
            :class="
              step.done
                ? 'text-ink-gray-5 line-through decoration-outline-gray-3'
                : index === currentIndex
                  ? 'font-medium text-ink-gray-9'
                  : 'text-ink-gray-5'
            "
          >
            {{ __(step.title) }}
          </p>

          <template v-if="index === currentIndex">
            <p class="mt-1 text-sm text-ink-gray-6">{{ __(step.help) }}</p>
            <div v-if="step.chips" class="mt-1.5 flex flex-wrap gap-1">
              <code
                v-for="chip in step.chips"
                :key="chip"
                class="rounded-2 bg-surface-gray-2 px-1.5 py-0.5 font-mono text-xs text-ink-gray-7"
              >
                {{ chip }}
              </code>
            </div>
            <div class="mt-2.5 flex flex-wrap items-center gap-2">
              <Button
                v-if="step.action"
                size="sm"
                variant="solid"
                :icon-left="step.action.icon"
                :loading="step.action.loading"
                :disabled="step.action.disabled"
                :label="__(step.action.label)"
                @click="step.action.run"
              />
              <Button
                v-if="step.target"
                size="sm"
                :variant="step.action ? 'ghost' : 'subtle'"
                icon-left="lucide-locate-fixed"
                :label="__('Show me')"
                @click="show(step.target)"
              />
              <a
                v-if="step.link"
                :href="step.link"
                target="_blank"
                rel="noopener"
                class="inline-flex items-center gap-1 text-sm text-ink-gray-6 underline underline-offset-2 hover:text-ink-gray-8"
              >
                {{ __('Meta guide') }}
                <span class="lucide-external-link size-3" aria-hidden="true" />
              </a>
            </div>
          </template>
        </div>
      </li>
    </ol>

    <div
      v-if="expanded && complete && instagram"
      class="flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-outline-gray-1 px-4 py-3 text-sm text-ink-gray-6"
    >
      <span class="font-medium text-ink-gray-7">{{ __('Next') }}</span>
      <button type="button" class="underline underline-offset-2 hover:text-ink-gray-8" @click="ui.openSettings('instagram')">
        {{ __('Choose how comments reach the inbox') }}
      </button>
      <a
        :href="APP_REVIEW"
        target="_blank"
        rel="noopener"
        class="inline-flex items-center gap-1 underline underline-offset-2 hover:text-ink-gray-8"
      >
        {{ __('Get Meta App Review to go live') }}
        <span class="lucide-external-link size-3" aria-hidden="true" />
      </a>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Button } from 'frappe-ui'
import { useUI } from '@/stores/ui'
import { translate as __ } from '@/translation'

const props = defineProps({
  doc: { type: Object, required: true },
  saved: { type: Boolean, default: false },
  hasToken: { type: Boolean, default: false },
  hasSecret: { type: Boolean, default: false },
  checking: { type: Boolean, default: false },
})

const emit = defineEmits(['test', 'connect'])

const ui = useUI()

const WHATSAPP_FIELDS = [
  'messages',
  'message_template_status_update',
  'message_template_quality_update',
  'phone_number_quality_update',
  'phone_number_name_update',
  'account_update',
]
const INSTAGRAM_FIELDS = ['messages', 'messaging_postbacks', 'messaging_seen', 'message_reactions', 'messaging_referral', 'comments']
const INSTAGRAM_GUIDE = 'https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login'
const WHATSAPP_GUIDE = 'https://developers.facebook.com/docs/whatsapp/cloud-api/get-started'
const WEBHOOK_GUIDE = 'https://developers.facebook.com/docs/whatsapp/cloud-api/guides/set-up-webhooks'
const APP_REVIEW = 'https://developers.facebook.com/docs/app-review'

const instagram = computed(() => props.doc.channel === 'Instagram')
const received = computed(() => !!props.doc.webhook_last_event_at)
const verified = computed(() => !!props.doc.webhook_verified_at || received.value)

const test = computed(() => ({
  key: 'test',
  title: 'Test the connection',
  help: instagram.value
    ? 'Checks the token, fills in the Instagram account ID and username, and subscribes the account to message webhooks.'
    : 'Checks the token and IDs with Meta and loads the number’s name, quality and limit.',
  done: props.doc.connection_status === 'Connected',
  target: 'test-connection',
  action: {
    label: 'Test connection',
    icon: 'lucide-plug-zap',
    loading: props.checking,
    disabled: !props.saved,
    run: () => emit('test'),
  },
}))

const save = computed(() => ({
  key: 'save',
  title: 'Name the account and create it',
  help: instagram.value
    ? 'Give it a name you’ll recognise, keep Channel on Instagram, then click Create at the top. The next steps unlock once it’s saved.'
    : 'Give it a name you’ll recognise, keep Channel on WhatsApp, then click Create at the top. The next steps unlock once it’s saved.',
  done: props.saved,
  target: 'account-fields',
}))

const whatsappSteps = computed(() => [
  save.value,
  {
    key: 'ids',
    title: 'Add the IDs and a permanent token',
    help: 'Phone number ID and WhatsApp Business account ID are in Meta → WhatsApp → API Setup. Create a system user token with whatsapp_business_messaging and whatsapp_business_management, so it never expires. Then save.',
    done: props.saved && props.hasToken && !!props.doc.phone_id && !!props.doc.business_id,
    target: 'meta-fields',
    link: WHATSAPP_GUIDE,
  },
  {
    key: 'secret',
    title: 'Add the app secret',
    help: 'Meta app → App settings → Basic → App secret. OneChat rejects every WhatsApp webhook until it’s set, so do this before the webhook steps. Then save.',
    done: props.hasSecret,
    target: 'app-secret',
  },
  test.value,
  {
    key: 'webhook',
    title: 'Verify the webhook',
    help: 'In Meta → WhatsApp → Configuration, paste the callback URL and verify token shown below, then click Verify and save.',
    done: verified.value,
    target: 'webhook-setup',
    link: WEBHOOK_GUIDE,
  },
  {
    key: 'fields',
    title: 'Subscribe to webhook fields and send a test message',
    help: 'Under Webhook fields, subscribe to these. Then send a WhatsApp message to this number; the step turns green when it arrives.',
    chips: WHATSAPP_FIELDS,
    done: received.value,
    target: 'webhook-setup',
  },
])

const instagramSteps = computed(() => [
  save.value,
  {
    key: 'secret',
    title: 'Add the Instagram app ID and app secret',
    help: 'Meta app → Instagram → API setup with Instagram login. Copy the Instagram app ID into App ID and the Instagram app secret into App secret, then save. Instagram webhooks are rejected until the secret is set.',
    done: props.saved && !!props.doc.app_id && props.hasSecret,
    target: 'meta-fields',
    link: INSTAGRAM_GUIDE,
  },
  {
    key: 'redirect',
    title: 'Add the redirect URL in Meta',
    help: 'Copy the redirect URL shown below into Meta → Instagram → API setup with Instagram login → Business login settings → OAuth redirect URIs.',
    done: props.hasToken,
    target: 'instagram-signin',
  },
  {
    key: 'connect',
    title: 'Connect with Instagram',
    help: 'Sign in with the Instagram professional account you want to use. You can also paste a token generated in the Meta app instead.',
    done: props.hasToken,
    action: {
      label: 'Connect with Instagram',
      icon: 'lucide-log-in',
      disabled: !props.saved || !props.hasSecret || !props.doc.app_id,
      run: () => emit('connect'),
    },
  },
  test.value,
  {
    key: 'webhook',
    title: 'Verify the webhook',
    help: 'In Meta → Instagram → API setup with Instagram login → Configure webhooks, paste the callback URL and verify token shown below, then click Verify and save.',
    done: verified.value,
    target: 'webhook-setup',
    link: INSTAGRAM_GUIDE,
  },
  {
    key: 'fields',
    title: 'Subscribe to webhook fields',
    help: 'Subscribe to these fields in the same Meta page.',
    chips: INSTAGRAM_FIELDS,
    done: received.value,
    target: 'webhook-setup',
  },
  {
    key: 'messages',
    title: 'Allow message access and send a test DM',
    help: 'In the Instagram app: Settings → Messages and story replies → Message controls → Connected tools → Allow access to messages. Then send a DM to this account from a tester profile; the step turns green when it arrives.',
    done: received.value,
  },
])

const steps = computed(() => (instagram.value ? instagramSteps.value : whatsappSteps.value))
const doneCount = computed(() => steps.value.filter((step) => step.done).length)
const complete = computed(() => doneCount.value === steps.value.length)
const currentIndex = computed(() => {
  const index = steps.value.findIndex((step) => !step.done)
  return index === -1 ? steps.value.length - 1 : index
})
const expanded = ref(!complete.value)

watch(complete, (value) => {
  if (value) expanded.value = false
})

function show(target) {
  const node = document.querySelector(`[data-tour="${target}"]`)
  if (!node) return
  node.scrollIntoView({ behavior: 'smooth', block: 'center' })
  node.classList.remove('onechat-guide-flash')
  void node.offsetWidth
  node.classList.add('onechat-guide-flash')
  setTimeout(() => node.classList.remove('onechat-guide-flash'), 1800)
}
</script>

<style>
.onechat-guide-flash {
  border-radius: 8px;
  animation: onechat-guide-flash 1.8s ease-out;
}

@keyframes onechat-guide-flash {
  0%,
  60% {
    box-shadow:
      0 0 0 4px var(--surface-base, #fff),
      0 0 0 6px var(--ink-blue-3, #3b82f6);
  }
  100% {
    box-shadow:
      0 0 0 4px transparent,
      0 0 0 6px transparent;
  }
}

@media (prefers-reduced-motion: reduce) {
  .onechat-guide-flash {
    animation: none;
    box-shadow: 0 0 0 2px var(--ink-blue-3, #3b82f6);
  }
}
</style>
