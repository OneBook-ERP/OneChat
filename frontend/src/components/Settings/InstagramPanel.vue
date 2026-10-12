<template>
  <SettingsHeader>
    <div class="flex items-start justify-between gap-3">
      <div class="min-w-0">
        <h2 class="text-lg font-semibold text-ink-gray-8">{{ __('Instagram') }}</h2>
        <p class="mt-1 text-base text-ink-gray-6">
          {{ __('How comments on your posts and reels reach the inbox. Automations for comments live in Flows.') }}
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

    <div v-else class="divide-y divide-outline-gray-1 pt-6">
      <SettingsRow
        :title="__('Show comments in the inbox')"
        :description="__(INBOX_HELP[form.ig_comments_in_inbox] || INBOX_HELP[INBOX[0]])"
      >
        <Select v-model="form.ig_comments_in_inbox" class="w-56" :options="INBOX.map((value) => ({ label: __(value), value }))" />
      </SettingsRow>

      <SettingsRow :title="__('Count comments as unread')" :description="__('Shown comments add to the unread badge.')">
        <Switch v-model="form.ig_comment_unread" />
      </SettingsRow>

      <SettingsRow
        :title="__('Include replies to comments')"
        :description="__('Off: only top-level comments come in. On: replies in comment threads come in too.')"
      >
        <Switch v-model="form.ig_comment_replies" />
      </SettingsRow>

      <SettingsRow :title="__('Hide comments with links')" :description="__('Hides comments containing a URL, usually spam.')">
        <Switch v-model="form.ig_comment_hide_links" />
      </SettingsRow>

      <div class="py-3">
        <FormControl
          v-model="form.ig_comment_hide_words"
          type="textarea"
          :rows="3"
          :label="__('Hide comments containing')"
          :placeholder="__('One word or phrase per line')"
          :description="__('Matching comments are hidden on Instagram and never start an automation.')"
        />
      </div>

      <div class="py-3">
        <LinkField
          v-model="form.ig_comment_label"
          doctype="OneChat Label"
          :label="__('Label commenters')"
          :description="__('Adds this label to everyone who comments, so you can filter or follow up later.')"
        />
      </div>

      <SettingsRow
        :title="__('Hide negative comments with AI')"
        :description="
          __('Each new comment is checked by the AI assistant set up in Settings → Assistant. Matching comments are hidden on Instagram.')
        "
      >
        <Switch v-model="form.ig_comment_hide_negative" />
      </SettingsRow>

      <SettingsRow
        v-if="form.ig_comment_hide_negative"
        :title="__('What to hide')"
        :description="__(LEVEL_HELP[form.ig_comment_negative_level] || '')"
      >
        <Select v-model="form.ig_comment_negative_level" class="w-56" :options="LEVELS.map((value) => ({ label: __(value), value }))" />
      </SettingsRow>

      <SettingsRow :title="__('Thank story mentions')" :description="__('Sends a DM when someone mentions you in their story.')">
        <Switch v-model="form.ig_story_thanks" />
      </SettingsRow>

      <template v-if="form.ig_story_thanks">
        <div class="py-3">
          <PersonalizedText
            v-model="form.ig_story_thanks_message"
            :rows="3"
            :label="__('Thank you message')"
            :variables="CONTACT_DETAILS"
            :placeholder="__('Thanks for the shoutout, {0}! 💛').format('{{first_name}}')"
          />
        </div>
        <div class="py-3">
          <FormControl v-model="form.ig_story_thanks_hours" type="number" :label="__('Thank the same person at most once every (hours)')" />
        </div>
      </template>
    </div>
  </SettingsBody>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import {
  Button,
  ErrorMessage,
  FormControl,
  Select,
  SettingsBody,
  SettingsHeader,
  SettingsRow,
  Skeleton,
  Switch,
  call,
  toast,
} from 'frappe-ui'
import LinkField from '@/components/Common/LinkField.vue'
import PersonalizedText from '@/components/Common/PersonalizedText.vue'
import { CONTACT_DETAILS } from '@/data/personalization'
import { errorMessage } from '@/utils/format'
import { translate as __ } from '@/translation'

const SETTINGS = 'OneChat Settings'
const INBOX = ['Matched or replied', 'All comments', 'None']
const INBOX_HELP = {
  'Matched or replied': 'Only comments that start an automation or get a reply appear as conversations.',
  'All comments': 'Every comment appears as a conversation, like a DM.',
  None: 'Comments never appear in the inbox. Automations still run, and private replies show up as normal chats.',
}
const LEVELS = ['Abusive only', 'Abusive and complaints']
const LEVEL_HELP = {
  'Abusive only': 'Insults, hate, harassment, threats, explicit content, spam and scams.',
  'Abusive and complaints': 'Everything above, plus angry complaints and negative reviews.',
}
const CHECKS = ['ig_comment_unread', 'ig_comment_replies', 'ig_comment_hide_links', 'ig_story_thanks', 'ig_comment_hide_negative']
const DEFAULTS = {
  ig_comments_in_inbox: INBOX[0],
  ig_comment_unread: true,
  ig_comment_replies: false,
  ig_comment_hide_links: false,
  ig_comment_hide_words: '',
  ig_comment_label: '',
  ig_comment_hide_negative: false,
  ig_comment_negative_level: 'Abusive only',
  ig_story_thanks: false,
  ig_story_thanks_message: '',
  ig_story_thanks_hours: 24,
}

const form = reactive({ ...DEFAULTS })
const saved = ref({ ...DEFAULTS })
const loading = ref(true)
const saving = ref(false)
const error = ref('')

const dirty = computed(() => Object.keys(DEFAULTS).some((key) => form[key] !== saved.value[key]))

function values() {
  return Object.fromEntries(Object.keys(DEFAULTS).map((key) => [key, CHECKS.includes(key) ? (form[key] ? 1 : 0) : form[key] || null]))
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const doc = await call('frappe.client.get', { doctype: SETTINGS, name: SETTINGS })
    for (const key of Object.keys(DEFAULTS)) {
      const value = doc[key]
      form[key] = CHECKS.includes(key) ? (value === undefined || value === null ? DEFAULTS[key] : !!Number(value)) : value || DEFAULTS[key]
    }
    saved.value = { ...form }
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
    await call('frappe.client.set_value', { doctype: SETTINGS, name: SETTINGS, fieldname: values() })
    saved.value = { ...form }
    toast.success(__('Saved'))
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>
