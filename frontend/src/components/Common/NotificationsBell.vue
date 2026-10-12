<template>
  <Popover v-if="rail" v-model:open="open" side="right" align="end" :offset="8">
    <template #trigger>
      <SidebarRailItem
        :label="__('Notifications')"
        variant="ghost"
        icon="lucide-bell"
        :active="open"
        :badge="feed.unread"
        badge-style="count"
      />
    </template>
    <template #default="{ close }">
      <div class="flex max-h-[min(38rem,calc(100dvh-4rem))] min-h-[28rem] h-[32rem] w-[26rem] max-w-[calc(100vw-5rem)] flex-col">
        <NotificationsList compact @close="close" />
      </div>
    </template>
  </Popover>

  <template v-else>
    <Button
      variant="ghost"
      size="lg"
      :label="feed.unread ? __('Notifications, {0} unread').format(feed.unread) : __('Notifications')"
      @click="open = true"
    >
      <template #icon>
        <span class="relative inline-flex">
          <span class="lucide-bell size-5" aria-hidden="true" />
          <span
            v-if="feed.unread"
            class="absolute -right-1.5 -top-1.5 min-w-4 rounded-full bg-surface-red-5 px-1 text-center text-[10px] font-semibold leading-4 text-ink-white"
            aria-hidden="true"
          >
            {{ feed.unread > 99 ? '99+' : feed.unread }}
          </span>
        </span>
      </template>
    </Button>
    <ResponsiveDialog v-model:open="open" :title="__('Notifications')">
      <div class="-mx-4 flex max-h-[70dvh] min-h-0 flex-col">
        <NotificationsList v-if="open" hide-title @close="open = false" />
      </div>
    </ResponsiveDialog>
  </template>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { Button, Popover, SidebarRailItem } from 'frappe-ui'
import NotificationsList from './NotificationsList.vue'
import ResponsiveDialog from './ResponsiveDialog.vue'
import { useNotificationFeed } from '@/stores/notificationFeed'
import { translate as __ } from '@/translation'

defineProps({ rail: { type: Boolean, default: false } })

const feed = useNotificationFeed()
const open = ref(false)

onMounted(() => feed.start())
</script>
