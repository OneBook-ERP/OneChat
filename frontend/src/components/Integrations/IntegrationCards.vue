<template>
  <section v-if="apps.length" class="flex flex-col gap-4">
    <div class="flex items-center justify-between">
      <h3 class="text-sm font-medium text-ink-gray-7">{{ __('Linked records') }}</h3>
      <Button
        variant="ghost"
        size="sm"
        icon-left="lucide-scan-search"
        :label="__('Find by phone')"
        :tooltip="__('Look for every record with this number in the connected apps')"
        :loading="busy === 'auto'"
        @click="findByPhone"
      />
    </div>

    <div v-if="loading && !state.links.length" class="flex flex-col gap-2">
      <Skeleton v-for="row in 2" :key="row" class="h-16 w-full" />
    </div>

    <div v-for="app in apps" :key="app.name" class="flex flex-col gap-2">
      <div class="flex items-center justify-between gap-2">
        <div class="flex min-w-0 items-center gap-1.5">
          <img v-if="app.logo" :src="app.logo" :alt="app.label" class="size-4 shrink-0 object-contain" />
          <span v-else :class="app.icon || 'lucide-blocks'" class="size-4 shrink-0 text-ink-gray-5" aria-hidden="true" />
          <TruncatedText class="truncate text-xs font-medium text-ink-gray-5" :text="app.label" />
          <span v-if="recordsOf(app.name).length > 1" class="text-xs tabular-nums text-ink-gray-4">{{ recordsOf(app.name).length }}</span>
        </div>
        <Button
          v-if="recordsOf(app.name).length"
          variant="ghost"
          size="sm"
          icon="lucide-plus"
          :label="__('Link another {0} record').format(app.label)"
          :tooltip="__('Link another record')"
          @click="startPicking(app)"
        />
      </div>

      <div v-if="picking === app.name" class="flex flex-col gap-2 rounded-4 border border-outline-gray-2 p-3">
        <Select v-model="pickDoctype" :options="doctypeOptions(app)" :placeholder="__('Record type')" />
        <LinkField v-if="pickDoctype" :key="pickDoctype" v-model="pickName" :doctype="pickDoctype" />
        <div class="flex justify-end gap-2">
          <Button variant="subtle" size="sm" :label="__('Cancel')" @click="picking = ''" />
          <Button
            variant="solid"
            size="sm"
            :label="__('Link')"
            :disabled="!pickDoctype || !pickName"
            :loading="busy === 'link'"
            @click="link(pickDoctype, pickName)"
          />
        </div>
      </div>

      <div v-if="recordsOf(app.name).length" class="flex flex-col gap-1">
        <div
          v-for="row in recordsOf(app.name)"
          :key="`${row.doctype}-${row.name}`"
          class="flex min-w-0 items-start gap-2.5 rounded-4 py-1"
          :class="{ 'opacity-90': !row.main }"
        >
          <Avatar :label="titleOf(app.name, row)" :size="row.main ? 'lg' : 'md'" class="mt-0.5 shrink-0" />
          <div class="min-w-0 flex-1">
            <component
              :is="session.user.is_admin ? 'a' : 'p'"
              v-bind="session.user.is_admin ? { href: recordUrl(row.doctype, row.name), target: '_blank', rel: 'noopener' } : {}"
              class="group flex min-w-0 items-center gap-1 font-semibold text-ink-gray-9"
              :class="row.main ? 'text-base' : 'text-sm'"
            >
              <TruncatedText class="truncate" :text="titleOf(app.name, row)" />
              <span
                v-if="session.user.is_admin"
                class="lucide-arrow-up-right size-3.5 shrink-0 text-ink-gray-5 group-hover:text-ink-gray-8"
                aria-hidden="true"
              />
            </component>
            <div class="mt-0.5 flex min-w-0 flex-wrap items-center gap-1.5">
              <Badge :theme="row.theme" variant="subtle" size="sm">{{ __(row.doctype) }}</Badge>
              <Badge v-if="row.status" variant="outline" size="sm">{{ __(row.status) }}</Badge>
              <span
                v-if="row.main && recordsOf(app.name).length > 1"
                class="inline-flex items-center gap-0.5 text-xs font-medium text-ink-amber-7"
              >
                <span class="lucide-star size-3" aria-hidden="true" />{{ __('Main') }}
              </span>
              <TruncatedText
                v-if="titleOf(app.name, row) !== row.name"
                class="min-w-0 truncate text-xs tabular-nums text-ink-gray-5"
                :text="row.name"
              />
            </div>
          </div>
          <Dropdown :options="recordMenu(row)" align="end">
            <Button variant="ghost" size="sm" icon="lucide-ellipsis" :label="__('Options for {0}').format(row.name)" />
          </Dropdown>
        </div>
      </div>

      <div
        v-else-if="picking !== app.name"
        class="flex items-center justify-between gap-2 rounded-4 border border-dashed border-outline-gray-2 px-3 py-2"
      >
        <TruncatedText as="p" class="truncate text-sm text-ink-gray-5" :text="__('Not linked yet')" />
        <Button size="sm" variant="ghost" icon-left="lucide-link" :label="__('Link')" @click="startPicking(app)" />
      </div>

      <div v-if="actionsOf(app.name).length" class="flex flex-wrap gap-1.5">
        <Button
          v-for="action in actionsOf(app.name)"
          :key="`${action.integration}-${action.key}`"
          size="sm"
          variant="subtle"
          :icon-left="action.icon"
          :label="action.label"
          :loading="busy === action.key"
          @click="perform(action)"
        />
      </div>

      <article
        v-for="card in cardsOf(app.name)"
        :key="`${card.integration}-${card.title}`"
        class="flex flex-col gap-2 rounded-4 border border-outline-gray-1 p-3"
      >
        <header class="flex items-center justify-between gap-2">
          <div class="flex min-w-0 items-center gap-1.5">
            <span v-if="card.icon" :class="card.icon" class="size-4 shrink-0 text-ink-gray-5" aria-hidden="true" />
            <TruncatedText as="h4" class="truncate text-sm font-medium text-ink-gray-8" :text="card.title" />
          </div>
          <a
            v-if="card.url && session.user.is_admin"
            :href="card.url"
            target="_blank"
            rel="noopener"
            class="shrink-0 text-xs text-ink-gray-5 hover:text-ink-gray-8"
          >
            {{ __('View all') }}
          </a>
        </header>

        <div v-if="card.badges?.length" class="flex flex-wrap gap-1">
          <Badge v-for="badge in card.badges" :key="badge.label" size="sm" variant="subtle" :theme="badge.theme || 'gray'">
            {{ badge.label }}
          </Badge>
        </div>

        <dl v-if="card.fields?.length" class="grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-1">
          <template v-for="field in card.fields" :key="field.label">
            <dt class="text-sm text-ink-gray-5">{{ field.label }}</dt>
            <TruncatedText as="dd" class="truncate text-right text-sm text-ink-gray-8" :text="field.value" />
          </template>
        </dl>

        <div v-if="card.people?.rows?.length" class="flex flex-col gap-1.5 border-t border-outline-gray-1 pt-2">
          <p class="text-xs font-medium text-ink-gray-5">{{ card.people.title }}</p>
          <div v-for="person in card.people.rows" :key="person.name" class="flex min-w-0 items-center gap-2">
            <Avatar :label="person.name" size="sm" class="shrink-0" />
            <TruncatedText class="min-w-0 flex-1 truncate text-sm text-ink-gray-8" :text="person.name" />
            <span v-if="person.detail" class="shrink-0 text-xs tabular-nums text-ink-gray-5">{{ person.detail }}</span>
          </div>
        </div>

        <template v-if="card.rows">
          <p v-if="!card.rows.length" class="text-sm text-ink-gray-5">{{ card.empty || __('Nothing here yet.') }}</p>
          <div v-else class="-mx-1 flex flex-col">
            <div v-for="row in card.rows" :key="row.title" class="flex items-center gap-1">
              <component
                :is="session.user.is_admin && row.url ? 'a' : 'div'"
                v-bind="session.user.is_admin && row.url ? { href: row.url, target: '_blank', rel: 'noopener' } : {}"
                class="flex min-w-0 flex-1 items-center gap-3 rounded-3 px-1 py-1.5"
                :class="{ 'hover:bg-surface-gray-1': session.user.is_admin && row.url }"
              >
                <div class="min-w-0 flex-1">
                  <TruncatedText as="p" class="truncate text-sm font-medium text-ink-gray-8" :text="row.title" />
                  <TruncatedText as="p" v-if="row.subtitle" class="truncate text-xs text-ink-gray-5" :text="row.subtitle" />
                </div>
                <div class="flex shrink-0 flex-col items-end gap-1">
                  <span v-if="row.value" class="text-sm tabular-nums text-ink-gray-8">{{ row.value }}</span>
                  <Badge v-if="row.status" size="sm" :theme="row.theme || 'gray'">{{ __(row.status) }}</Badge>
                </div>
              </component>
              <Dropdown v-if="row.actions?.length" :options="rowMenu(card, row)" align="end">
                <Button
                  variant="ghost"
                  size="sm"
                  icon="lucide-ellipsis-vertical"
                  :label="__('Actions for {0}').format(row.title)"
                  :loading="busy === rowKey(row)"
                />
              </Dropdown>
            </div>
          </div>
        </template>
      </article>
    </div>

    <div v-if="otherActions.length" class="flex flex-wrap gap-1.5">
      <Button
        v-for="action in otherActions"
        :key="`${action.integration}-${action.key}`"
        size="sm"
        variant="subtle"
        :icon-left="action.icon"
        :label="action.label"
        :loading="busy === action.key"
        @click="perform(action)"
      />
    </div>

    <ErrorMessage :message="error" />

    <component
      :is="dialog.component"
      v-if="dialog.component"
      v-model:open="dialog.open"
      :contact="contact"
      :action="dialog.action"
      @done="(result) => apply(result, result.message)"
    />
  </section>

  <p v-else-if="session.user.is_admin && integrations.fetched" class="rounded-4 bg-surface-gray-1 px-3 py-3 text-sm text-ink-gray-5">
    {{ __('Link contacts to records in your other apps, such as ERPNext customers, from Settings → Integrations.') }}
  </p>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { computed, markRaw, reactive, ref, watch } from 'vue'
import { Avatar, Badge, Button, Dropdown, ErrorMessage, Select, Skeleton, toast } from 'frappe-ui'
import LinkField from '@/components/Common/LinkField.vue'
import {
  autoLinkContact,
  contactIntegrations,
  integrations,
  linkApps,
  linkContact,
  makeMainLink,
  recordUrl,
  runAction,
  runRowAction,
  unlinkRecord,
} from '@/data/integrations'
import { dialogs } from './dialogs'
import { session } from '@/data/session'
import { errorMessage } from '@/utils/format'
import { translate as __ } from '@/translation'

const props = defineProps({
  contact: { type: String, required: true },
  referenceDoctype: { type: String, default: null },
  referenceDocname: { type: String, default: null },
  linked: { type: Array, default: () => [] },
})

const emit = defineEmits(['changed'])

const state = reactive({ cards: [], actions: [], links: [] })
const loading = ref(false)
const busy = ref('')
const error = ref('')
const picking = ref('')
const pickDoctype = ref('')
const pickName = ref('')
const dialog = reactive({ component: null, action: null, open: false })

const apps = computed(() => linkApps.value)
const otherActions = computed(() => state.actions.filter((action) => !apps.value.some((app) => app.name === action.integration)))

function recordsOf(integration) {
  return state.links.filter((row) => row.integration === integration).sort((a, b) => Number(b.main) - Number(a.main))
}

function titleOf(integration, row) {
  if (row.main) {
    const headline = state.cards.find((card) => card.integration === integration && card.headline)?.headline
    if (headline) return headline
  }
  return row.title || row.name
}

function cardsOf(integration) {
  return state.cards.filter((card) => card.integration === integration)
}

function actionsOf(integration) {
  return state.actions.filter((action) => action.integration === integration)
}

function doctypeOptions(app) {
  return app.link_doctypes.map((row) => ({ label: __(row.doctype), value: row.doctype }))
}

function recordMenu(row) {
  return [
    session.user.is_admin && {
      label: __('Open in Desk'),
      icon: 'lucide-external-link',
      onClick: () => window.open(recordUrl(row.doctype, row.name), '_blank', 'noopener'),
    },
    !row.main && { label: __('Make main record'), icon: 'lucide-star', onClick: () => makeMain(row) },
    { label: __('Unlink'), icon: 'lucide-unlink', theme: 'red', onClick: () => unlinkOne(row) },
  ].filter(Boolean)
}

async function load() {
  if (!props.contact || !apps.value.length) return

  loading.value = true
  error.value = ''
  try {
    Object.assign(state, await contactIntegrations(props.contact))
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    loading.value = false
  }
}

function apply(result, message) {
  state.cards = result.cards || []
  state.actions = result.actions || []
  if (result.links) state.links = result.links
  picking.value = ''
  emit('changed', result)
  if (message) toast.success(message)
}

async function attempt(key, work) {
  busy.value = key
  error.value = ''
  try {
    await work()
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    busy.value = ''
  }
}

function startPicking(app) {
  pickDoctype.value = app.link_doctypes[0]?.doctype || ''
  pickName.value = ''
  picking.value = app.name
}

function link(doctype, name) {
  return attempt('link', async () => {
    const result = await linkContact(props.contact, doctype, name)
    apply(result, __('Linked to {0}').format(name))
  })
}

function unlinkOne(row) {
  return attempt('link', async () => {
    const result = await unlinkRecord(props.contact, row.doctype, row.name)
    apply(result, __('Unlinked {0}').format(row.name))
  })
}

function makeMain(row) {
  return attempt('link', async () => {
    const result = await makeMainLink(props.contact, row.doctype, row.name)
    apply(result, __('{0} is now the main record').format(row.name))
  })
}

function findByPhone() {
  return attempt('auto', async () => {
    const result = await autoLinkContact(props.contact)
    if (result.found?.length) {
      apply(result, __('Linked to {0}').format(result.found.join(', ')))
    } else {
      error.value = __('No new record with this phone number was found.')
    }
  })
}

function perform(action) {
  if (action.dialog && dialogs[action.dialog]) {
    Object.assign(dialog, { component: markRaw(dialogs[action.dialog]), action, open: true })
    return
  }

  return attempt(action.key, async () => {
    const result = await runAction(props.contact, action)
    apply(result, result.message || __('Done'))
  })
}

function rowKey(row) {
  return `row-${row.doctype}-${row.name}`
}

function rowMenu(card, row) {
  return row.actions.map((action) => ({
    label: action.label,
    icon: action.icon,
    onClick: () =>
      attempt(rowKey(row), async () => {
        const result = await runRowAction(props.contact, card.integration, action, row)
        apply(result, result.message || __('Done'))
      }),
  }))
}

watch(() => [props.contact, props.referenceDoctype, props.referenceDocname, (props.linked || []).join('|'), apps.value.length], load, {
  immediate: true,
})
</script>
