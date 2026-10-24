const SCENES = {
  timeline: ['history'],
  notifications: ['bell'],
  conversation: ['inbox', 'message', 'messages'],
  login: ['users', 'user', 'contact'],
  data: ['search', 'database', 'table', 'layers'],
  messages: ['send', 'megaphone', 'mail'],
  task: ['git-fork', 'workflow', 'sparkles', 'plug', 'bot', 'list', 'clipboard', 'scroll', 'square-check'],
  templates: ['notebook', 'layout-template', 'file', 'qr-code'],
  event: ['calendar', 'clock', 'alarm'],
  access: ['shield', 'lock', 'key'],
  favourite: ['star', 'tag', 'bookmark', 'heart'],
  wallet: ['wallet', 'receipt', 'coins'],
  'credit-card': ['credit-card', 'banknote'],
  trash: ['trash', 'archive'],
  image: ['image'],
  dashboard: ['chart', 'bar-chart', 'gauge', 'activity'],
  network: ['circle-alert', 'cloud-off', 'alert', 'triangle-alert', 'wifi-off'],
  call: ['smartphone', 'monitor', 'phone'],
  product: ['package', 'store', 'shopping'],
}

export function sceneFor(icon) {
  const name = String(icon || '').replace(/^lucide-/, '')
  for (const [scene, prefixes] of Object.entries(SCENES)) {
    if (prefixes.some((prefix) => name.startsWith(prefix))) return scene
  }
  return 'product'
}
