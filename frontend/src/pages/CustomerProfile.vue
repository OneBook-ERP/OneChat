<template>
  <AppHeader :tail="[{ label: title }]" :back="{ name: 'Contacts' }">
    <template #actions>
      <Dropdown :options="menu" align="end">
        <Button variant="ghost" icon="lucide-ellipsis" :label="__('More actions')" />
      </Dropdown>
      <Button variant="solid" icon-left="lucide-message-circle" :label="__('Message')" @click="openChat" />
    </template>
  </AppHeader>

  <div class="px-3 pb-10 pt-5 sm:px-5">
    <div class="mx-auto w-full max-w-[1100px]">
      <ErrorMessage v-if="error" :message="error" class="mb-4" />

      <div class="grid grid-cols-1 gap-6 lg:grid-cols-[320px_minmax(0,1fr)]">
        <aside class="flex min-w-0 flex-col gap-5">
          <section class="flex items-center gap-3">
            <Skeleton v-if="!profile" class="size-16 rounded-full" />
            <Avatar v-else :image="profile.profile_image" :label="title" size="3xl" />
            <div class="min-w-0 flex-1">
              <Skeleton v-if="!profile" class="h-6 w-40 rounded-full" />
              <template v-else>
                <div class="flex min-w-0 items-center gap-2">
                  <TruncatedText as="p" class="truncate text-xl font-semibold text-ink-gray-9" :text="title" />
                  <ChannelIcon :channel="profile.channel" show-whatsapp class="size-5 shrink-0" />
                </div>
                <a
                  v-if="profile.instagram_username"
                  :href="`https://instagram.com/${profile.instagram_username}`"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="block text-sm text-ink-gray-6 hover:text-ink-gray-8"
                >
                  @{{ profile.instagram_username }}
                </a>
                <a
                  v-if="profile.mobile_no"
                  :href="`tel:${profile.mobile_no}`"
                  class="block text-sm tabular-nums text-ink-gray-6 hover:text-ink-gray-8"
                >
                  {{ formatPhone(profile.mobile_no) }}
                </a>
                <a
                  v-if="profile.email"
                  :href="`mailto:${profile.email}`"
                  class="block truncate text-sm text-ink-gray-5 hover:text-ink-gray-8"
                >
                  {{ profile.email }}
                </a>
              </template>
            </div>
          </section>

          <div v-if="profile" class="flex flex-col gap-2.5">
            <div class="flex flex-wrap gap-1.5">
              <Badge
                v-if="profile.reference_doctype"
                :theme="linkMeta(profile.reference_doctype).theme"
                :label="__(profile.reference_doctype)"
              />
              <Badge v-if="profile.opted_out" theme="red" :label="__('Opted out')" />
              <Badge v-if="profile.conversation_status" variant="outline" :label="__(profile.conversation_status)" />
              <LabelBadges v-if="profile.labels?.length" :names="profile.labels" />
            </div>
            <div v-if="profile.assigned_to || profile.team" class="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-ink-gray-6">
              <span v-if="profile.assigned_to" class="inline-flex items-center gap-1.5">
                <span class="lucide-user-check size-4 shrink-0 text-ink-gray-5" aria-hidden="true" />
                {{ __('Assigned to {0}').format(profile.assigned_name || profile.assigned_to) }}
              </span>
              <span v-if="profile.team" class="inline-flex items-center gap-1.5">
                <span class="lucide-users size-4 shrink-0 text-ink-gray-5" aria-hidden="true" />
                {{ profile.team }}
              </span>
            </div>
          </div>

          <div
            v-if="duplicates.length"
            class="flex items-start gap-2 rounded-4 border border-outline-amber-2 bg-surface-amber-1 px-3 py-2.5"
          >
            <span class="lucide-copy mt-0.5 size-4 shrink-0 text-ink-amber-7" aria-hidden="true" />
            <div class="min-w-0 flex-1 text-sm">
              <p class="font-medium text-ink-gray-8">{{ __('Possible duplicate') }}</p>
              <p v-for="row in duplicates.slice(0, 1)" :key="row.name" class="truncate text-ink-gray-7">
                <router-link :to="{ name: 'CustomerProfile', params: { contact: row.name } }" class="underline underline-offset-2">
                  {{ row.contact_name || row.name }}
                </router-link>
                · {{ row.reasons.join(', ') }}
                <span v-if="duplicates.length > 1" class="text-ink-gray-5"> · {{ __('+{0} more').format(duplicates.length - 1) }}</span>
              </p>
            </div>
            <Button size="sm" variant="ghost" :label="__('Review')" @click="router.push({ name: 'Duplicates' })" />
          </div>

          <CustomerScores
            v-if="profile?.scores?.scores_updated_at !== undefined"
            :contact="contact"
            :scores="profile.scores"
            @updated="setScores"
          />

          <CustomerStats :stats="stats" :loading="!profile" columns="grid-cols-2 [&>*:last-child:nth-child(odd)]:col-span-2" />

          <div v-if="memberOf.length" class="flex flex-col gap-2">
            <p class="text-sm font-medium text-ink-gray-6">{{ __('In segments') }}</p>
            <div class="flex flex-wrap gap-1.5">
              <Button
                v-for="row in memberOf"
                :key="row.name"
                size="sm"
                variant="subtle"
                icon-left="lucide-users-round"
                :label="row.segment_name"
                @click="router.push({ name: 'Segments' })"
              />
            </div>
          </div>

          <div v-if="profile" class="flex items-center justify-between gap-3 rounded-4 border border-outline-gray-1 px-3 py-2.5">
            <div class="min-w-0">
              <p class="text-base font-medium text-ink-gray-8">{{ __('Marketing messages') }}</p>
              <p class="text-sm text-ink-gray-5">
                {{
                  profile.opted_out
                    ? __('Opted out. Broadcasts and marketing templates are blocked.')
                    : __('Subscribed. They can reply STOP to opt out.')
                }}
              </p>
            </div>
            <Switch
              v-if="session.user.is_admin"
              :model-value="!profile.opted_out"
              :disabled="toggling"
              :aria-label="__('Subscribed to marketing messages')"
              @update:model-value="setConsent"
            />
          </div>

          <IntegrationCards
            v-if="profile"
            :contact="contact"
            :reference-doctype="profile.reference_doctype"
            :reference-docname="profile.reference_docname"
            @changed="load"
          />
        </aside>

        <section class="min-w-0">
          <h2 class="mb-3 text-lg font-semibold text-ink-gray-9">{{ __('Timeline') }}</h2>
          <CustomerTimeline ref="timeline" :contact="contact" filterable />
        </section>
      </div>
    </div>
  </div>

  <ContactFormDialog v-model:open="editOpen" :name="contact" @saved="load" @deleted="router.push({ name: 'Contacts' })" />
</template>

<script setup>
import ChannelIcon from '@/components/Common/ChannelIcon.vue'
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Avatar, Badge, Button, Dropdown, ErrorMessage, Skeleton, Switch, call, toast } from 'frappe-ui'
import CustomerScores from '@/components/Customer/CustomerScores.vue'
import CustomerStats from '@/components/Customer/CustomerStats.vue'
import CustomerTimeline from '@/components/Customer/CustomerTimeline.vue'
import IntegrationCards from '@/components/Integrations/IntegrationCards.vue'
import LabelBadges from '@/components/Labels/LabelBadges.vue'
import AppHeader from '@/components/Layouts/AppHeader.vue'
import ContactFormDialog from '@/components/Contacts/ContactFormDialog.vue'
import { customerProfile } from '@/data/customer'
import { deskUrl } from '@/data/inbox'
import { linkMeta } from '@/data/integrations'
import { contactSegments } from '@/data/segments'
import { session } from '@/data/session'
import { useUI } from '@/stores/ui'
import { errorMessage, formatPhone } from '@/utils/format'
import { recall, remember } from '@/utils/swr'
import { translate as __ } from '@/translation'

defineProps({ compact: { type: Boolean, default: false } })

const route = useRoute()
const router = useRouter()
const ui = useUI()

const profile = ref(null)
const error = ref('')
const toggling = ref(false)
const timeline = ref(null)
const memberOf = ref([])
const duplicates = ref([])

const contact = computed(() => route.params.contact)
const editOpen = ref(false)
const title = computed(
  () =>
    profile.value?.contact_name ||
    profile.value?.mobile_no ||
    (profile.value?.instagram_username && `@${profile.value.instagram_username}`) ||
    contact.value,
)
const stats = computed(() => [...(profile.value?.record_stats || []), ...(profile.value?.stats || [])])

const menu = computed(() => [
  { label: __('Edit contact'), icon: 'lucide-pencil', onClick: () => (editOpen.value = true) },
  {
    label: __('Open in desk'),
    icon: 'lucide-external-link',
    onClick: () => window.open(deskUrl('OneChat Contact', contact.value), '_blank', 'noopener'),
    condition: () => session.user.is_admin,
  },
  { label: __('Delete contact'), icon: 'lucide-trash-2', theme: 'red', onClick: remove },
])

async function load() {
  error.value = ''
  const key = `profile:${contact.value}`
  const cached = recall(key)
  if (cached && !profile.value) profile.value = cached
  try {
    profile.value = await customerProfile(contact.value)
    remember(key, profile.value)
  } catch (err) {
    error.value = errorMessage(err)
  }
  contactSegments(contact.value)
    .then((rows) => (memberOf.value = rows))
    .catch(() => (memberOf.value = []))
  call('onechat.inbox.duplicates.for_contact', { contact: contact.value })
    .then((rows) => (duplicates.value = rows))
    .catch(() => (duplicates.value = []))
}

function setScores(scores) {
  profile.value = { ...profile.value, scores }
  contactSegments(contact.value)
    .then((rows) => (memberOf.value = rows))
    .catch(() => {})
}

function openChat() {
  router.push({ name: 'Inbox', params: { contact: contact.value } })
}

async function setConsent(subscribed) {
  toggling.value = true
  try {
    await call('onechat.inbox.consent.set_opted_out', { contact: contact.value, opted_out: subscribed ? 0 : 1 })
    toast.success(subscribed ? __('Subscribed to marketing messages') : __('Opted out of marketing messages'))
    await load()
    timeline.value?.reload()
  } catch (err) {
    toast.error(errorMessage(err))
  } finally {
    toggling.value = false
  }
}

function remove() {
  ui.confirm({
    title: __('Delete this contact?'),
    message: __('Their conversation history stays, but the contact record is removed.'),
    action: __('Delete'),
    theme: 'red',
    onConfirm: async () => {
      await call('frappe.client.delete', { doctype: 'OneChat Contact', name: contact.value })
      toast.success(__('Deleted'))
      router.push({ name: 'Contacts' })
    },
  })
}

watch(
  contact,
  (value) => {
    profile.value = null
    memberOf.value = []
    duplicates.value = []
    if (value) load()
  },
  { immediate: true },
)
</script>
