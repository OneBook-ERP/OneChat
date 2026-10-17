export const SECTIONS = [
  {
    key: 'inbox',
    doctype: 'OneChat Contact',
    label: 'Inbox',
    subtitle: 'WhatsApp conversations',
    icon: 'lucide-inbox',
    route: '/inbox',
    links: { name: 'Inbox', after: 1 },
    labels: { name: 'Inbox', after: 1 },
    groups: [
      {
        items: [
          { label: 'All conversations', icon: 'lucide-message-square-text', to: { name: 'Inbox' } },
          { label: 'Unread', icon: 'lucide-mail', to: { name: 'Inbox', query: { view: 'unread' } } },
          { label: 'Assigned to me', icon: 'lucide-user-check', to: { name: 'Inbox', query: { view: 'mine' } } },
          { label: 'Mentions', icon: 'lucide-at-sign', to: { name: 'Inbox', query: { view: 'mentions' } } },
          { label: 'Overdue', icon: 'lucide-timer', to: { name: 'Inbox', query: { view: 'overdue' } } },
          { label: 'Follow-ups', icon: 'lucide-bell-ring', to: { name: 'Inbox', query: { view: 'followups' } } },
          { label: 'Snoozed', icon: 'lucide-alarm-clock', to: { name: 'Inbox', query: { view: 'snoozed' } } },
        ],
      },
      {
        label: 'Status',
        items: [
          { label: 'Open', icon: 'lucide-circle-dot', to: { name: 'Inbox', query: { status: 'open' } } },
          { label: 'Pending', icon: 'lucide-clock', to: { name: 'Inbox', query: { status: 'pending' } } },
          { label: 'Resolved', icon: 'lucide-circle-check', to: { name: 'Inbox', query: { status: 'resolved' } } },
        ],
      },
      {
        label: 'Instagram',
        items: [{ label: 'Comments', icon: 'lucide-message-square-text', to: { name: 'Comments' }, channel: 'Instagram' }],
      },
    ],
  },
  {
    key: 'contacts',
    doctype: 'OneChat Contact',
    label: 'Contacts',
    subtitle: 'People you talk to',
    icon: 'lucide-users',
    route: '/contacts',
    links: { name: 'Contacts', after: 0 },
    groups: [
      {
        items: [
          { label: 'All contacts', icon: 'lucide-contact', to: { name: 'Contacts' } },
          { label: 'Segments', icon: 'lucide-users-round', to: { name: 'Segments' } },
          { label: 'Duplicates', icon: 'lucide-copy', to: { name: 'Duplicates' } },
        ],
      },
      {
        label: 'Workspace',
        items: [{ label: 'Notes', icon: 'lucide-notebook-pen', to: { name: 'Notes' }, doctype: 'OneChat Note' }],
      },
    ],
  },
  {
    key: 'campaigns',
    label: 'Campaigns',
    subtitle: 'Templates and broadcasts',
    icon: 'lucide-megaphone',
    route: '/campaigns/templates',
    admin: true,
    groups: [
      {
        items: [
          { label: 'Templates', icon: 'lucide-layout-template', to: { name: 'Templates' }, doctype: 'WhatsApp Templates' },
          { label: 'Broadcasts', icon: 'lucide-send', to: { name: 'Broadcasts' }, doctype: 'Bulk WhatsApp Message' },
          { label: 'Recipient lists', icon: 'lucide-list-checks', to: { name: 'RecipientLists' }, doctype: 'WhatsApp Recipient List' },
          { label: 'Forms', icon: 'lucide-clipboard-list', to: { name: 'Forms' }, doctype: 'WhatsApp Flow' },
          { label: 'Media library', icon: 'lucide-images', to: { name: 'Media' }, doctype: 'OneChat Media' },
          { label: 'Links & QR', icon: 'lucide-qr-code', to: { name: 'ChatLinks' }, doctype: 'OneChat Chat Link' },
          { label: 'Catalog', icon: 'lucide-shopping-bag', to: { name: 'Catalog' }, integration: 'erpnext' },
        ],
      },
      {
        label: 'Reports',
        items: [
          { label: 'Delivery report', icon: 'lucide-chart-no-axes-column', to: { name: 'DeliveryReport' }, doctype: 'OneChat Message' },
        ],
      },
    ],
  },
  {
    key: 'automation',
    label: 'Automation',
    subtitle: 'Rules and flows',
    icon: 'lucide-workflow',
    route: '/automation/rules',
    admin: true,
    groups: [
      {
        items: [
          { label: 'Notification rules', icon: 'lucide-bell-ring', to: { name: 'Rules' } },
          { label: 'Flows', icon: 'lucide-git-fork', to: { name: 'Flows' }, doctype: 'OneChat Flow' },
          { label: 'Auto replies', icon: 'lucide-message-square-reply', to: { name: 'AutoReplies' } },
        ],
      },
      {
        label: 'Monitoring',
        items: [{ label: 'Execution logs', icon: 'lucide-scroll-text', to: { name: 'ExecutionLogs' } }],
      },
    ],
  },
  {
    key: 'insights',
    doctype: 'OneChat Message',
    label: 'Insights',
    subtitle: 'How messaging is going',
    icon: 'lucide-bar-chart-3',
    route: '/insights',
    admin: true,
    groups: [
      {
        items: [
          { label: 'Overview', icon: 'lucide-gauge', to: { name: 'Insights' } },
          { label: 'Conversations', icon: 'lucide-messages-square', to: { name: 'Insights', query: { tab: 'conversations' } } },
          { label: 'Team', icon: 'lucide-users', to: { name: 'Insights', query: { tab: 'team' } } },
          { label: 'Automation', icon: 'lucide-bot', to: { name: 'Insights', query: { tab: 'automation' } } },
          { label: 'Campaigns', icon: 'lucide-megaphone', to: { name: 'Insights', query: { tab: 'campaigns' } } },
          { label: 'Catalog orders', icon: 'lucide-shopping-bag', to: { name: 'Insights', query: { tab: 'orders' } } },
          { label: 'Costs', icon: 'lucide-wallet', to: { name: 'Insights', query: { tab: 'costs' } } },
        ],
      },
    ],
  },
  {
    key: 'audit',
    label: 'Audit log',
    subtitle: 'Who did what',
    icon: 'lucide-shield-check',
    route: '/audit',
    systemManager: true,
    groups: [
      {
        items: [{ label: 'All activity', icon: 'lucide-activity', to: { name: 'AuditLog' } }],
      },
      {
        label: 'Activity',
        items: [
          { label: 'Messages sent', icon: 'lucide-send', to: { name: 'AuditLog', query: { category: 'messages' } } },
          { label: 'Assignments', icon: 'lucide-user-check', to: { name: 'AuditLog', query: { category: 'assignments' } } },
          { label: 'Status changes', icon: 'lucide-circle-check', to: { name: 'AuditLog', query: { category: 'status' } } },
          { label: 'Consent', icon: 'lucide-bell-off', to: { name: 'AuditLog', query: { category: 'consent' } } },
          { label: 'Labels', icon: 'lucide-tags', to: { name: 'AuditLog', query: { category: 'labels' } } },
          { label: 'Notes', icon: 'lucide-notebook-pen', to: { name: 'AuditLog', query: { category: 'notes' } } },
        ],
      },
    ],
  },
]

const VIEW_KEYS = {}

function viewKeys(name) {
  if (!VIEW_KEYS[name]) {
    const keys = new Set()
    for (const section of SECTIONS) {
      if (section.links?.name === name) keys.add('link')
      if (section.labels?.name === name) keys.add('label')
      for (const group of section.groups) {
        for (const item of group.items) {
          if (item.to?.name === name) Object.keys(item.to.query || {}).forEach((key) => keys.add(key))
        }
      }
    }
    VIEW_KEYS[name] = [...keys]
  }
  return VIEW_KEYS[name]
}

export function matches(route, to) {
  if (route.name !== to.name) return false

  return viewKeys(to.name).every((key) => (route.query[key] || null) === (to.query?.[key] || null))
}

export function withLinks(section, linkTypes) {
  if (!section?.links || !linkTypes.length) return section

  const group = {
    label: 'Linked to',
    items: linkTypes.map((row) => ({
      label: row.label,
      icon: row.icon,
      to: { name: section.links.name, query: { link: row.doctype } },
    })),
  }
  const groups = [...section.groups]
  groups.splice(section.links.after + 1, 0, group)

  return { ...section, groups }
}

export function withLabels(section, labels, dots) {
  if (!section?.labels || !labels.length) return section

  const group = {
    label: 'Labels',
    items: labels.map((row) => ({
      label: row.label_name || row.name,
      raw: true,
      dot: dots[row.color] || dots.gray,
      to: { name: section.labels.name, query: { label: row.name } },
    })),
  }
  const groups = [...section.groups]
  groups.splice(section.labels.after + 1, 0, group)

  return { ...section, groups }
}
