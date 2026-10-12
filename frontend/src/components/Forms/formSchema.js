import { translate as __ } from '@/translation'

export const FIELD_TYPES = [
  { type: 'TextInput', label: 'Short answer', icon: 'lucide-text-cursor-input', group: 'Inputs', input: true, text: true },
  { type: 'TextArea', label: 'Paragraph', icon: 'lucide-align-left', group: 'Inputs', input: true, text: true },
  { type: 'DatePicker', label: 'Date', icon: 'lucide-calendar', group: 'Inputs', input: true },
  { type: 'RadioButtonsGroup', label: 'Single choice', icon: 'lucide-circle-dot', group: 'Choices', input: true, choice: true },
  { type: 'CheckboxGroup', label: 'Multiple choice', icon: 'lucide-list-checks', group: 'Choices', input: true, choice: true },
  { type: 'Dropdown', label: 'Dropdown', icon: 'lucide-square-chevron-down', group: 'Choices', input: true, choice: true },
  { type: 'OptIn', label: 'Opt-in', icon: 'lucide-square-check', group: 'Choices', input: true },
  { type: 'TextHeading', label: 'Heading', icon: 'lucide-heading-1', group: 'Content' },
  { type: 'TextSubheading', label: 'Subheading', icon: 'lucide-heading-2', group: 'Content' },
  { type: 'TextBody', label: 'Body text', icon: 'lucide-pilcrow', group: 'Content' },
  { type: 'TextCaption', label: 'Caption', icon: 'lucide-type', group: 'Content' },
  { type: 'Image', label: 'Image', icon: 'lucide-image', group: 'Content' },
  { type: 'EmbeddedLink', label: 'Link to screen', icon: 'lucide-link', group: 'Content' },
  { type: 'Footer', label: 'Footer button', icon: 'lucide-rectangle-horizontal', group: 'Content' },
]

export const FIELD_GROUPS = ['Inputs', 'Choices', 'Content']

export const CATEGORIES = [
  'SIGN_UP',
  'SIGN_IN',
  'APPOINTMENT_BOOKING',
  'LEAD_GENERATION',
  'CONTACT_US',
  'CUSTOMER_SUPPORT',
  'SURVEY',
  'OTHER',
]

export const VERSIONS = ['7.3', '7.2', '7.1', '7.0', '6.3', '6.2', '6.1', '6.0', '5.1']

export const STATUS_THEMES = {
  Draft: 'gray',
  Published: 'green',
  Deprecated: 'red',
  Blocked: 'red',
  Throttled: 'amber',
}

const FALLBACK = { type: '', label: 'Field', icon: 'lucide-square', group: 'Content' }

let counter = 0

export function uid() {
  counter += 1
  return `k${Date.now().toString(36)}${counter}`
}

export function fieldDef(type) {
  return FIELD_TYPES.find((item) => item.type === type) || { ...FALLBACK, type, label: type }
}

export function isInput(type) {
  return !!fieldDef(type).input
}

export function isChoice(type) {
  return !!fieldDef(type).choice
}

export function isText(type) {
  return !!fieldDef(type).text
}

export function categoryLabel(value) {
  if (!value) return ''
  const text = value.replace(/_/g, ' ').toLowerCase()

  return __(text.charAt(0).toUpperCase() + text.slice(1))
}

export function slug(text) {
  const out = String(text || '')
    .toLowerCase()
    .normalize('NFKD')
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 40)

  return /^[0-9]/.test(out) ? `f_${out}` : out
}

export function screenSlug(text) {
  return String(text || '')
    .toUpperCase()
    .normalize('NFKD')
    .replace(/[^A-Z]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 40)
}

function unique(base, taken) {
  if (!taken.includes(base)) return base

  const letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
  for (const letter of letters) {
    const candidate = `${base}_${letter}`
    if (!taken.includes(candidate)) return candidate
  }

  return `${base}_${uid()
    .replace(/[^a-z]/g, '')
    .toUpperCase()}`
}

function uniqueName(base, taken) {
  if (!taken.includes(base)) return base

  let index = 2
  while (taken.includes(`${base}_${index}`)) index += 1

  return `${base}_${index}`
}

export function uniqueScreenId(base, screens) {
  return unique(
    base === 'SUCCESS' ? 'SUCCESS_SCREEN' : base || 'SCREEN',
    screens.map((screen) => screen.screen_id),
  )
}

export function newScreen(screens, title) {
  const screenTitle = title || __('Screen {0}').format(screens.length + 1)
  const base = screenSlug(screenTitle) || 'SCREEN'

  return {
    key: uid(),
    name: null,
    autoId: true,
    screen_id: uniqueScreenId(base, screens),
    screen_title: screenTitle,
    terminal: false,
    refresh_on_back: false,
    layout_type: 'SingleColumnLayout',
    success_message: '',
    fields: [],
  }
}

export function newField(type, screens) {
  const def = fieldDef(type)
  const taken = screens.flatMap((screen) => screen.fields.map((field) => field.field_name))
  const label = type === 'Footer' ? __('Continue') : ''

  return {
    key: uid(),
    name: null,
    field_type: type,
    field_name: uniqueName(slug(def.label) || 'field', taken),
    autoName: true,
    label,
    required: false,
    enabled: true,
    init_value: '',
    min_chars: null,
    max_chars: null,
    helper_text: '',
    error_message: '',
    options: def.choice
      ? [
          { id: 'option_1', title: __('Option 1') },
          { id: 'option_2', title: __('Option 2') },
        ]
      : [],
  }
}

export function blankForm() {
  return {
    name: null,
    modified: null,
    flow_name: __('Untitled form'),
    whatsapp_account: '',
    status: 'Draft',
    flow_id: '',
    category: 'OTHER',
    description: '',
    flow_cta: 'Open Form',
    data_api_version: '6.0',
    endpoint_uri: '',
    preview_url: '',
  }
}

export function blankScreens() {
  const screen = newScreen([], __('Your details'))
  screen.terminal = true
  screen.success_message = __('Thanks, we have received your response.')

  return [screen]
}

function parseOptions(value) {
  if (Array.isArray(value)) return value
  if (!value) return []

  try {
    const parsed = JSON.parse(value)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function intOrNull(value) {
  if (value === '' || value === null || value === undefined) return null
  const number = parseInt(value, 10)

  return Number.isNaN(number) || number === 0 ? null : number
}

const byIdx = (a, b) => (a.idx || 0) - (b.idx || 0)

export function readDoc(doc) {
  const form = {}
  for (const key of Object.keys(blankForm())) form[key] = doc[key] ?? blankForm()[key]
  form.name = doc.name
  form.modified = doc.modified

  const screens = [...(doc.screens || [])].sort(byIdx).map((row) => ({
    key: uid(),
    name: row.name,
    autoId: false,
    screen_id: row.screen_id || '',
    screen_title: row.screen_title || '',
    terminal: !!row.terminal,
    refresh_on_back: !!row.refresh_on_back,
    layout_type: row.layout_type || 'SingleColumnLayout',
    success_message: row.success_message || '',
    fields: [],
  }))

  const orphans = []
  for (const row of [...(doc.fields || [])].sort(byIdx)) {
    const field = {
      key: uid(),
      name: row.name,
      field_type: row.field_type,
      field_name: row.field_name || '',
      autoName: false,
      label: row.label || '',
      required: !!row.required,
      enabled: row.enabled === undefined || row.enabled === null ? true : !!row.enabled,
      init_value: row.init_value || '',
      min_chars: intOrNull(row.min_chars),
      max_chars: intOrNull(row.max_chars),
      helper_text: row.helper_text || '',
      error_message: row.error_message || '',
      options: parseOptions(row.options).map((option) => ({ ...option })),
    }
    field.autoName = isInput(field.field_type) && !!field.label && field.field_name === slug(field.label)

    const screen = screens.find((item) => item.screen_id === row.screen)
    if (screen) screen.fields.push(field)
    else orphans.push({ ...field, screen: row.screen })
  }

  return { form, screens, orphans }
}

export function writeDoc(form, screens, orphans = []) {
  const doc = {
    doctype: 'WhatsApp Flow',
    flow_name: String(form.flow_name || '').trim(),
    whatsapp_account: form.whatsapp_account || null,
    category: form.category || 'OTHER',
    description: form.description || '',
    flow_cta: form.flow_cta || '',
    data_api_version: form.data_api_version || '6.0',
    endpoint_uri: form.endpoint_uri || '',
  }

  if (form.name) {
    doc.name = form.name
    doc.modified = form.modified
    doc.status = form.status || 'Draft'
    doc.flow_id = form.flow_id || null
    doc.preview_url = form.preview_url || null
  }

  doc.screens = screens.map((screen, index) => ({
    ...(screen.name ? { name: screen.name } : {}),
    idx: index + 1,
    screen_id: screen.screen_id,
    screen_title: screen.screen_title,
    terminal: screen.terminal ? 1 : 0,
    refresh_on_back: screen.refresh_on_back ? 1 : 0,
    layout_type: screen.layout_type || 'SingleColumnLayout',
    success_message: screen.terminal ? screen.success_message || '' : '',
  }))

  const rows = [
    ...screens.flatMap((screen) => screen.fields.map((field) => ({ field, screen: screen.screen_id }))),
    ...orphans.map((field) => ({ field, screen: field.screen })),
  ]

  doc.fields = rows.map(({ field, screen }, index) => ({
    ...(field.name ? { name: field.name } : {}),
    idx: index + 1,
    screen,
    field_name: field.field_name,
    field_type: field.field_type,
    label: field.label || '',
    required: field.required ? 1 : 0,
    enabled: field.enabled ? 1 : 0,
    init_value: field.init_value || '',
    min_chars: isText(field.field_type) ? intOrNull(field.min_chars) : null,
    max_chars: isText(field.field_type) ? intOrNull(field.max_chars) : null,
    helper_text: field.helper_text || '',
    error_message: field.error_message || '',
    options: isChoice(field.field_type)
      ? JSON.stringify(field.options.map((option) => ({ ...option, id: String(option.id || '').trim(), title: option.title || '' })))
      : '',
  }))

  return doc
}

const NAME_PATTERN = /^[A-Za-z_][A-Za-z0-9_]*$/
const SCREEN_PATTERN = /^[A-Za-z_]+$/

function fieldTitle(field) {
  return field.label || field.field_name || __(fieldDef(field.field_type).label)
}

export function checkForm(form, screens) {
  const issues = []
  const add = (level, message, screen = null, field = null) =>
    issues.push({ level, message, screenKey: screen?.key || null, fieldKey: field?.key || null })

  if (!String(form.flow_name || '').trim()) add('error', __('Give the form a name.'))
  if (!form.whatsapp_account) add('error', __('Pick a WhatsApp account in Settings.'))
  if (!screens.length) add('error', __('Add at least one screen.'))

  const terminals = screens.filter((screen) => screen.terminal)
  if (screens.length && !terminals.length) add('error', __('Mark one screen as the final screen.'))
  if (terminals.length > 1) add('error', __('Only one screen can be the final screen.'), terminals[1])
  if (terminals.length === 1 && screens.indexOf(terminals[0]) !== screens.length - 1) {
    add('warning', __('Screens after the final screen are never shown.'), terminals[0])
  }

  const screenIds = screens.map((screen) => screen.screen_id)
  const allNames = {}

  for (const screen of screens) {
    const title = screen.screen_title || screen.screen_id || __('Untitled screen')

    if (!screen.screen_id) add('error', __('{0}: the screen ID is empty.').format(title), screen)
    else if (!SCREEN_PATTERN.test(screen.screen_id)) {
      add('error', __('{0}: the screen ID can only use letters and underscores.').format(title), screen)
    } else if (screen.screen_id === 'SUCCESS') add('error', __('{0}: SUCCESS is a reserved screen ID.').format(title), screen)
    if (screenIds.filter((id) => id === screen.screen_id).length > 1) {
      add('error', __('{0}: another screen uses the ID {1}.').format(title, screen.screen_id), screen)
    }
    if (!String(screen.screen_title || '').trim()) add('error', __('A screen has no title.'), screen)

    const enabled = screen.fields.filter((field) => field.enabled)
    if (!enabled.length) add('warning', __('{0} has no fields.').format(title), screen)
    if (enabled.filter((field) => field.field_type === 'Footer').length > 1) {
      add('error', __('{0} has more than one footer button.').format(title), screen)
    }

    const seen = {}
    for (const field of screen.fields) {
      if (!field.enabled) continue
      const name = fieldTitle(field)

      if (!field.field_name) add('error', __('{0}: the field name is empty.').format(name), screen, field)
      else if (!NAME_PATTERN.test(field.field_name)) {
        add('error', __('{0}: the field name can only use letters, numbers and underscores.').format(name), screen, field)
      }

      if (isInput(field.field_type) && field.field_name) {
        if (seen[field.field_name]) {
          add('error', __('{0}: the field name {1} is already used on this screen.').format(name, field.field_name), screen, field)
        } else if (allNames[field.field_name]) {
          add(
            'warning',
            __('{0}: {1} is also used on {2}; the later answer wins.').format(name, field.field_name, allNames[field.field_name]),
            screen,
            field,
          )
        }
        seen[field.field_name] = true
        allNames[field.field_name] = allNames[field.field_name] || title
      }

      if (isInput(field.field_type) && !field.label) add('warning', __('{0} has no label.').format(name), screen, field)

      if (isChoice(field.field_type)) {
        const ids = field.options.map((option) => String(option.id || '').trim())
        if (!field.options.length) add('error', __('{0}: add at least one option.').format(name), screen, field)
        else if (ids.some((id) => !id)) add('error', __('{0}: every option needs an ID.').format(name), screen, field)
        else if (new Set(ids).size !== ids.length) add('error', __('{0}: option IDs must be unique.').format(name), screen, field)
        if (field.options.some((option) => !String(option.title || '').trim())) {
          add('error', __('{0}: every option needs a title.').format(name), screen, field)
        }
      }

      if (isText(field.field_type) && field.min_chars && field.max_chars && Number(field.min_chars) > Number(field.max_chars)) {
        add('error', __('{0}: the minimum length is more than the maximum.').format(name), screen, field)
      }

      if (['TextHeading', 'TextSubheading', 'TextBody', 'TextCaption'].includes(field.field_type) && !field.label) {
        add('error', __('{0}: add the text to show.').format(name), screen, field)
      }

      if (field.field_type === 'Image' && !field.init_value) add('error', __('{0}: add the image source.').format(name), screen, field)

      if (field.field_type === 'EmbeddedLink' && !screenIds.includes(field.init_value)) {
        add('error', __('{0}: pick the screen this link opens.').format(name), screen, field)
      }
    }
  }

  return issues.sort((a, b) => (a.level === b.level ? 0 : a.level === 'error' ? -1 : 1))
}

export function docMethod(name, method, args) {
  return { dt: 'WhatsApp Flow', dn: name, method, ...(args ? { args } : {}) }
}
