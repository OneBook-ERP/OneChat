<template>
  <ResponsiveDialog v-model:open="open" :title="row?.label || ''" size="lg">
    <template v-if="row" #default>
      <div class="flex flex-col gap-5">
        <div class="flex items-start gap-3">
          <IntegrationLogo :logo="row.logo" :icon="row.icon" :label="row.label" size="lg" />
          <div class="min-w-0">
            <p class="text-sm text-ink-gray-5">{{ row.category }}</p>
            <p class="mt-1 text-base text-ink-gray-7">{{ row.description }}</p>
          </div>
        </div>

        <div v-if="row.features?.length">
          <p class="mb-2 text-sm font-medium text-ink-gray-8">{{ __('What you get') }}</p>
          <ul class="flex flex-col gap-2">
            <li v-for="feature in row.features" :key="feature" class="flex items-start gap-2 text-base text-ink-gray-7">
              <span class="lucide-check mt-0.5 size-4 shrink-0 text-ink-green-6" aria-hidden="true" />{{ feature }}
            </li>
          </ul>
        </div>

        <div v-if="row.where?.length || row.sites_help" class="flex flex-col gap-2">
          <p class="text-sm font-medium text-ink-gray-8">{{ __('Where it runs') }}</p>
          <div
            v-for="site in row.where"
            :key="site.label"
            class="flex items-start gap-3 rounded-4 border border-outline-gray-2 px-3 py-2.5"
          >
            <span
              :class="site.remote ? 'lucide-globe' : 'lucide-server'"
              class="mt-0.5 size-4 shrink-0 text-ink-gray-6"
              aria-hidden="true"
            />
            <div class="min-w-0 flex-1">
              <TruncatedText
                as="p"
                class="truncate text-sm font-medium text-ink-gray-9"
                :text="site.remote ? site.label : __('This site')"
              />
              <TruncatedText
                as="p"
                class="truncate text-xs text-ink-gray-5"
                :text="
                  [
                    site.remote ? __('Another site') : site.label,
                    site.auth,
                    site.user && __('as {0}').format(site.user),
                    site.detail,
                    site.remote && (site.last_event_at ? __('last event {0}').format(timeAgo(site.last_event_at)) : __('no events yet')),
                  ]
                    .filter(Boolean)
                    .join(' · ')
                "
              />
            </div>
            <Badge size="sm" variant="subtle" :theme="site.ready ? 'green' : 'gray'" :label="site.ready ? __('Ready') : __('Not ready')" />
          </div>
          <p v-if="row.sites_help" class="text-sm leading-5 text-ink-gray-6">{{ row.sites_help }}</p>
        </div>

        <div v-if="row.link_doctypes?.length">
          <p class="mb-2 text-sm font-medium text-ink-gray-8">{{ __('Contacts can be linked to') }}</p>
          <div class="flex flex-wrap gap-1.5">
            <Badge v-for="link in row.link_doctypes" :key="link.doctype" :theme="link.theme || 'gray'" :label="link.label">
              <template #prefix>
                <span :class="link.icon" class="size-3" aria-hidden="true" />
              </template>
            </Badge>
          </div>
        </div>

        <div v-if="!row.installed && !row.setup" class="rounded-4 bg-surface-gray-1 p-3">
          <p class="text-sm font-medium text-ink-gray-8">{{ __('Install the {0} app on this site first').format(row.app) }}</p>
          <p class="mt-1 text-sm text-ink-gray-6">{{ __('Ask whoever manages your server to run:') }}</p>
          <ScrollArea orientation="horizontal" class="mt-2 rounded-3 bg-surface-base">
            <pre class="px-2.5 py-2 font-mono text-xs text-ink-gray-8">{{ command }}</pre>
          </ScrollArea>
        </div>
      </div>
    </template>

    <template v-if="row" #actions>
      <div class="flex w-full flex-wrap items-center justify-end gap-2">
        <Button v-if="row.docs_url" variant="ghost" icon-left="lucide-external-link" :label="__('Documentation')" :link="row.docs_url" />
        <Button
          v-if="row.setup"
          variant="solid"
          icon-left="lucide-settings-2"
          :label="row.enabled && row.installed ? __('Manage connection') : __('Set up')"
          @click="emit('setup')"
        />
        <Button
          v-else-if="row.installed && row.enabled"
          variant="subtle"
          icon-left="lucide-unplug"
          :loading="busy"
          :label="__('Disconnect')"
          @click="emit('disconnect')"
        />
        <Button
          v-else-if="row.installed"
          variant="solid"
          icon-left="lucide-plug"
          :loading="busy"
          :label="__('Connect')"
          @click="emit('connect')"
        />
      </div>
    </template>
  </ResponsiveDialog>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { computed } from 'vue'
import { Badge, Button, ScrollArea } from 'frappe-ui'
import ResponsiveDialog from '@/components/Common/ResponsiveDialog.vue'
import IntegrationLogo from './IntegrationLogo.vue'
import { timeAgo } from '@/utils/format'
import { translate as __ } from '@/translation'

const props = defineProps({
  row: { type: Object, default: null },
  busy: { type: Boolean, default: false },
})

const emit = defineEmits(['connect', 'disconnect', 'setup'])

const open = defineModel('open', { type: Boolean, default: false })

const command = computed(() => `bench get-app ${props.row?.app}\nbench --site <site> install-app ${props.row?.app}`)
</script>
