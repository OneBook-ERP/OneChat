import { computed, h, markRaw } from 'vue'
import ChannelIcon from '@/components/Common/ChannelIcon.vue'
import { useNumbers } from '@/stores/numbers'
import { translate as __ } from '@/translation'

export function channelIcon(channel) {
  return markRaw({ render: () => h(ChannelIcon, { channel, showWhatsapp: true, class: 'size-4 shrink-0' }) })
}

export function useNumberMenu() {
  const numbers = useNumbers()
  if (!numbers.loaded) numbers.load()

  function switches(label, rows, option) {
    if (rows.length < 2) return null
    return {
      group: label,
      options: rows.map((row) => ({
        switch: true,
        switchValue: row.shown,
        disabled: numbers.saving,
        ...option(row),
      })),
    }
  }

  const numberMenu = computed(() =>
    [
      switches(__('Accounts shown'), numbers.rows, (row) => ({
        label: [row.label, row.phone, row.unread ? __('{0} unread').format(row.unread) : ''].filter(Boolean).join(' · '),
        icon: channelIcon(row.channel),
        onClick: (value) => numbers.toggle(row.name, value),
      })),
      switches(__('Teams shown'), numbers.teamRows, (row) => ({
        label: row.label,
        icon: 'lucide-users',
        onClick: (value) => numbers.toggleTeam(row.name, value),
      })),
      {
        group: __('Numbers'),
        hideLabel: true,
        options: [
          {
            label: __('Show everything'),
            icon: 'lucide-eye',
            condition: () => numbers.scoped,
            onClick: numbers.showAll,
          },
        ],
      },
    ].filter(Boolean),
  )

  return { numbers, numberMenu }
}
