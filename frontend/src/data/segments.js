import { call } from 'frappe-ui'

const METHOD = 'onechat.inbox.segments.'

export const VALUE_GROUPS = [
  { value: 'Champion', theme: 'green', icon: 'lucide-trophy' },
  { value: 'Loyal', theme: 'green', icon: 'lucide-heart-handshake' },
  { value: 'New customer', theme: 'blue', icon: 'lucide-sparkles' },
  { value: 'Promising', theme: 'blue', icon: 'lucide-trending-up' },
  { value: 'Needs attention', theme: 'amber', icon: 'lucide-bell-ring' },
  { value: 'At risk', theme: 'red', icon: 'lucide-triangle-alert' },
  { value: 'Lost', theme: 'gray', icon: 'lucide-user-x' },
  { value: 'Prospect', theme: 'gray', icon: 'lucide-sprout' },
]

export const OP_LABELS = {
  gt: 'is more than',
  gte: 'is at least',
  lt: 'is less than',
  lte: 'is at most',
  eq: 'is exactly',
  between: 'is between',
  within: 'in the last',
  over: 'more than … ago',
  never: 'never',
  in: 'is any of',
  not_in: 'is none of',
  is: 'is',
  contains: 'contains',
  set: 'is set',
  not_set: 'is not set',
  yes: 'yes',
  no: 'no',
  has_any: 'has any of',
  has_none: 'has none of',
}

export const NO_VALUE = ['never', 'set', 'not_set', 'yes', 'no']

export function groupMeta(value) {
  return VALUE_GROUPS.find((row) => row.value === value) || { value, theme: 'gray', icon: 'lucide-circle' }
}

export const ENGAGEMENT_BANDS = [
  {
    key: 'highly_engaged',
    label: 'Highly engaged',
    min: 70,
    max: 100,
    theme: 'green',
    icon: 'lucide-flame',
    hint: 'Replies often and recently',
  },
  {
    key: 'engaged',
    label: 'Engaged',
    min: 40,
    max: 69,
    theme: 'blue',
    icon: 'lucide-message-circle-heart',
    hint: 'Talks with you now and then',
  },
  { key: 'quiet', label: 'Quiet', min: 15, max: 39, theme: 'amber', icon: 'lucide-message-circle-dashed', hint: 'Rarely replies' },
  { key: 'inactive', label: 'Inactive', min: 0, max: 14, theme: 'gray', icon: 'lucide-moon', hint: 'No replies in the last 90 days' },
]

export function engagementBand(key) {
  return ENGAGEMENT_BANDS.find((band) => band.key === key) || null
}

export function engagementTheme(score) {
  if (score >= 70) return { label: 'Highly engaged', theme: 'green' }
  if (score >= 40) return { label: 'Engaged', theme: 'blue' }
  if (score >= 15) return { label: 'Quiet', theme: 'amber' }
  return { label: 'Inactive', theme: 'gray' }
}

export function segmentFields() {
  return call(`${METHOD}fields`)
}

export function segmentList() {
  return call(`${METHOD}segments`)
}

export function previewSegment(rules, match) {
  return call(`${METHOD}preview`, { rules: JSON.stringify(rules), match })
}

export function saveSegment({ name, segment_name, description, match, rules }) {
  return call(`${METHOD}save_segment`, { name, segment_name, description, match, rules: JSON.stringify(rules) })
}

export function deleteSegment(name) {
  return call(`${METHOD}delete_segment`, { name })
}

export function contactSegments(contact) {
  return call(`${METHOD}contact_segments`, { contact })
}

export function refreshScores(contact) {
  return call('onechat.inbox.scores.refresh', { contact })
}

export function refreshAllScores() {
  return call('onechat.inbox.scores.refresh_all')
}
