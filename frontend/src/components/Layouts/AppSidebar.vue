<template>
  <Sidebar width="14rem" disable-collapse class="border-r">
    <SidebarHeader :title="__(section.label)" :subtitle="subtitle" :menu-items="menuItems" :show-logo="false" />

    <ScrollArea class="min-h-0 flex-1" viewport-class="px-2 pt-0.5 pb-10">
      <SectionNav :section="section" :counts="section.key === 'inbox' ? inboxCounts : {}" />
    </ScrollArea>
  </Sidebar>
</template>

<script setup>
import { computed } from 'vue'
import { ScrollArea, Sidebar, SidebarHeader } from 'frappe-ui'
import SectionNav from './SectionNav.vue'
import { channelIcon } from '@/composables/useNumberMenu'
import { useSection } from '@/composables/useSection'
import { counts, inbox, inboxCounts, setChannel } from '@/data/inbox'
import { translate as __ } from '@/translation'

const { section } = useSection()

const SUBTITLES = {
  all: 'All conversations',
  WhatsApp: 'WhatsApp conversations',
  Instagram: 'Instagram conversations',
}

const channels = computed(() => counts.data?.channels || [])
const switchable = computed(() => section.value?.key === 'inbox' && channels.value.length > 1)

const subtitle = computed(() => (switchable.value ? __(SUBTITLES[inbox.channel || 'all']) : __(section.value?.subtitle || '')))

const menuItems = computed(() =>
  switchable.value
    ? [
        { label: __('All channels'), icon: 'lucide-messages-square', onClick: () => setChannel(null) },
        ...channels.value.map((channel) => ({
          label: __(channel),
          icon: channelIcon(channel),
          onClick: () => setChannel(channel),
        })),
      ]
    : [],
)
</script>
