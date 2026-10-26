import { CATALOG } from './catalog'

export { CATEGORIES } from './catalog'

export const COLORS = {
  violet: { chip: 'bg-surface-violet-2 text-ink-violet-7', mini: 'fb-mini-violet' },
  amber: { chip: 'bg-surface-amber-2 text-ink-amber-7', mini: 'fb-mini-amber' },
  cyan: { chip: 'bg-surface-cyan-2 text-ink-cyan-7', mini: 'fb-mini-cyan' },
  blue: { chip: 'bg-surface-blue-2 text-ink-blue-7', mini: 'fb-mini-blue' },
  green: { chip: 'bg-surface-green-2 text-ink-green-7', mini: 'fb-mini-green' },
  red: { chip: 'bg-surface-red-2 text-ink-red-7', mini: 'fb-mini-red' },
  orange: { chip: 'bg-surface-orange-2 text-ink-orange-7', mini: 'fb-mini-orange' },
  teal: { chip: 'bg-surface-teal-2 text-ink-teal-7', mini: 'fb-mini-teal' },
  purple: { chip: 'bg-surface-purple-2 text-ink-purple-7', mini: 'fb-mini-purple' },
  gray: { chip: 'bg-surface-gray-3 text-ink-gray-7', mini: 'fb-mini-gray' },
}

export const DOC_EVENTS = [
  { value: 'before_insert', label: 'Before insert' },
  { value: 'after_insert', label: 'After insert' },
  { value: 'before_validate', label: 'Before validate' },
  { value: 'validate', label: 'Validate' },
  { value: 'on_update', label: 'On update' },
  { value: 'before_submit', label: 'Before submit' },
  { value: 'on_submit', label: 'On submit' },
  { value: 'before_cancel', label: 'Before cancel' },
  { value: 'on_cancel', label: 'On cancel' },
  { value: 'on_trash', label: 'On trash' },
  { value: 'after_delete', label: 'After delete' },
  { value: 'before_update_after_submit', label: 'Before update after submit' },
  { value: 'on_update_after_submit', label: 'On update after submit' },
]

export const FLOW_TRIGGER_TYPES = ['WhatsApp Incoming', 'ERPNext Document Event', 'Scheduled', 'Manual', 'Webhook']

const TRIGGER_LABELS = {
  'WhatsApp Incoming': 'Customer message',
  'ERPNext Document Event': 'Record changes',
  Scheduled: 'Schedule',
  Manual: 'Started by an agent',
}

export function triggerLabel(value) {
  return TRIGGER_LABELS[value] || value
}

export const FLOW_CATEGORIES = ['Customer Service', 'Sales', 'Support', 'Notifications', 'Workflow Automation', 'Other']

const doctypeField = (key = 'doctype', label = 'DocType') => ({ key, label, type: 'doctype', required: true })

const docnameField = (placeholder = 'context.erp.name') => ({
  key: 'docname',
  label: 'Document name',
  type: 'expression',
  required: true,
  placeholder,
})

const itemHint = 'Use item to refer to each entry of the array.'

const LEGACY = [
  {
    type: 'webhook_trigger',
    hidden: true,
    label: 'Webhook',
    description: 'HTTP webhook endpoint',
    icon: 'lucide-webhook',
    color: 'cyan',
    category: 'trigger',
    triggerType: 'Webhook',
    fields: [],
  },
  {
    type: 'email_trigger',
    hidden: true,
    label: 'Email received',
    description: 'When an email arrives',
    icon: 'lucide-mail',
    color: 'blue',
    category: 'trigger',
    runnable: false,
    fields: [],
  },
  {
    type: 'whatsapp_trigger',
    hidden: true,
    label: 'WhatsApp message',
    description: 'When a message is received',
    icon: 'lucide-message-circle',
    color: 'green',
    category: 'trigger',
    triggerType: 'WhatsApp Incoming',
    hint: 'Leave the filters empty to react to every incoming message.',
    fields: [
      { key: 'keyword', label: 'Keyword', type: 'text', placeholder: 'order status' },
      { key: 'template_name', label: 'Replying to template', type: 'template' },
      { key: 'button', label: 'Button text', type: 'text', placeholder: 'Confirm' },
    ],
  },
  {
    type: 'create_document',
    hidden: true,
    label: 'Create document',
    description: 'Create a new document',
    icon: 'lucide-file-plus',
    color: 'green',
    category: 'advanced',
    hint: 'The new document is available as context.created_doc.',
    fields: [doctypeField(), { key: 'fields', label: 'Field values', type: 'keyvalue', doctypeKey: 'doctype' }],
  },
  {
    type: 'update_document',
    hidden: true,
    label: 'Update document',
    description: 'Change fields on a document',
    icon: 'lucide-file-pen',
    color: 'blue',
    category: 'advanced',
    fields: [
      doctypeField(),
      docnameField('context.erp.name'),
      { key: 'fields', label: 'Field values', type: 'keyvalue', doctypeKey: 'doctype' },
    ],
  },
  {
    type: 'delete_document',
    hidden: true,
    label: 'Delete document',
    description: 'Delete a document',
    icon: 'lucide-file-x',
    color: 'red',
    category: 'advanced',
    fields: [doctypeField(), docnameField('context.erp.name')],
  },
  {
    type: 'send_whatsapp',
    hidden: true,
    label: 'Send WhatsApp',
    description: 'Send a WhatsApp template',
    icon: 'lucide-message-circle',
    color: 'green',
    category: 'advanced',
    fields: [
      { key: 'to', label: 'To (phone)', type: 'expression', required: true, placeholder: 'context.erp.doc.contact_mobile' },
      { key: 'template_name', label: 'Template', type: 'template', required: true },
    ],
  },
  {
    type: 'if_else',
    hidden: true,
    label: 'If / else',
    description: 'Branch on a condition',
    icon: 'lucide-git-branch',
    color: 'amber',
    category: 'advanced',
    outputs: [
      { id: 'true', label: 'Yes' },
      { id: 'false', label: 'No' },
    ],
    hint: 'Connect the Yes and No handles. Each branch runs only when the condition matches.',
    fields: [
      {
        key: 'condition',
        label: 'Condition',
        type: 'expression',
        required: true,
        python: true,
        placeholder: "context['vars']['total'] > 5000",
      },
    ],
  },
  {
    type: 'switch',
    hidden: true,
    label: 'Switch',
    description: 'Match one of many values',
    icon: 'lucide-split',
    color: 'orange',
    category: 'advanced',
    hint: "The match is stored in context.switch_result. Put a condition such as context['switch_result']['case'] == 'Paid' on each outgoing connection.",
    fields: [
      { key: 'value', label: 'Value to switch on', type: 'expression', required: true, placeholder: 'context.erp.doc.status' },
      { key: 'cases', label: 'Cases', type: 'list', placeholder: 'Paid' },
    ],
  },
  {
    type: 'loop',
    hidden: true,
    label: 'Loop',
    description: 'Iterate over items',
    icon: 'lucide-repeat',
    color: 'violet',
    category: 'advanced',
    fields: [
      { key: 'items', label: 'Items array', type: 'expression', required: true, placeholder: 'context.erp.doc.items' },
      { key: 'item_variable', label: 'Item variable name', type: 'text', default: 'item', placeholder: 'item' },
    ],
  },
  {
    type: 'error_handler',
    hidden: true,
    label: 'Error handler',
    description: 'Catch and handle errors',
    icon: 'lucide-triangle-alert',
    color: 'red',
    category: 'advanced',
    runnable: false,
    fields: [],
  },
  {
    type: 'retry',
    hidden: true,
    label: 'Retry',
    description: 'Retry on failure',
    icon: 'lucide-rotate-ccw',
    color: 'amber',
    category: 'advanced',
    runnable: false,
    fields: [],
  },
  {
    type: 'transform_data',
    hidden: true,
    label: 'Transform data',
    description: 'Reshape a value',
    icon: 'lucide-code',
    color: 'violet',
    category: 'advanced',
    fields: [
      { key: 'source', label: 'Source data', type: 'expression', placeholder: 'context.vars.order' },
      { key: 'transform', label: 'Transform expression', type: 'expression', required: true, placeholder: 'context.data.customer_name' },
      { key: 'output_variable', label: 'Output variable', type: 'text', default: 'transformed_data', placeholder: 'transformed_data' },
    ],
  },
  {
    type: 'python_expression',
    hidden: true,
    label: 'Expression',
    description: 'Resolve a value into context',
    icon: 'lucide-braces',
    color: 'purple',
    category: 'advanced',
    fields: [
      { key: 'expression', label: 'Expression', type: 'expression', required: true, placeholder: 'context.erp.doc.grand_total' },
      { key: 'output_variable', label: 'Output variable', type: 'text', default: 'result', placeholder: 'result' },
    ],
  },
  {
    type: 'filter_array',
    hidden: true,
    label: 'Filter array',
    description: 'Keep matching items',
    icon: 'lucide-filter',
    color: 'cyan',
    category: 'advanced',
    hint: itemHint,
    fields: [
      { key: 'array', label: 'Array', type: 'expression', required: true, placeholder: 'context.doc_list' },
      { key: 'condition', label: 'Filter condition', type: 'expression', required: true, placeholder: 'context.item.qty' },
    ],
  },
  {
    type: 'map_array',
    hidden: true,
    label: 'Map array',
    description: 'Transform each item',
    icon: 'lucide-map',
    color: 'green',
    category: 'advanced',
    hint: itemHint,
    fields: [
      { key: 'array', label: 'Array', type: 'expression', required: true, placeholder: 'context.doc_list' },
      { key: 'transform', label: 'Transform expression', type: 'expression', required: true, placeholder: 'context.item.item_name' },
    ],
  },
  {
    type: 'merge_objects',
    hidden: true,
    label: 'Merge objects',
    description: 'Combine data objects',
    icon: 'lucide-merge',
    color: 'amber',
    category: 'advanced',
    runnable: false,
    fields: [],
  },
  {
    type: 'get_doc',
    hidden: true,
    label: 'Get document',
    description: 'Fetch a document by name',
    icon: 'lucide-database',
    color: 'blue',
    category: 'advanced',
    hint: 'The document is available as context.fetched_doc.',
    fields: [doctypeField(), docnameField('context.erp.name or DOC-0001')],
  },
  {
    type: 'submit_doc',
    hidden: true,
    label: 'Submit document',
    description: 'Submit a document',
    icon: 'lucide-circle-check',
    color: 'green',
    category: 'advanced',
    hint: 'Only submittable documents can be submitted.',
    fields: [doctypeField(), docnameField()],
  },
  {
    type: 'cancel_doc',
    hidden: true,
    label: 'Cancel document',
    description: 'Cancel a submitted document',
    icon: 'lucide-circle-x',
    color: 'red',
    category: 'advanced',
    hint: 'Only submitted documents can be cancelled.',
    fields: [doctypeField(), docnameField()],
  },
  {
    type: 'attach_file',
    hidden: true,
    label: 'Attach file',
    description: 'Attach a file to a document',
    icon: 'lucide-paperclip',
    color: 'gray',
    category: 'advanced',
    runnable: false,
    fields: [],
  },
]

export const NODE_TYPES = [...CATALOG, ...LEGACY]

const ALIASES = {
  create_sales_order: 'create_from_order',
  erpnext_doc_event_trigger: 'doc_event_trigger',
  whatsapp_incoming_trigger: 'whatsapp_trigger',
  create_doc: 'create_document',
  update_doc: 'update_document',
  delete_doc: 'delete_document',
  whatsapp_send_template: 'send_whatsapp',
  if_condition: 'if_else',
  switch_case: 'switch',
  delay: 'wait',
  get_document: 'get_doc',
  submit_document: 'submit_doc',
  cancel_document: 'cancel_doc',
  workflow_action: 'apply_workflow',
  erpnext_workflow_action: 'apply_workflow',
}

const BY_TYPE = Object.fromEntries(NODE_TYPES.map((def) => [def.type, def]))

const FALLBACK = {
  type: 'unknown',
  label: 'Unknown step',
  description: '',
  icon: 'lucide-circle-help',
  color: 'gray',
  category: 'action',
  runnable: false,
  fields: [],
}

export function nodeDef(type) {
  return BY_TYPE[type] || BY_TYPE[ALIASES[type]] || { ...FALLBACK, type, label: type || FALLBACK.label }
}

const TRIGGER_TYPES = new Set(NODE_TYPES.filter((def) => def.category === 'trigger').map((def) => def.type))

export function isTrigger(type) {
  return TRIGGER_TYPES.has(type) || String(type || '').endsWith('_trigger')
}

export function outputsOf(type, config = {}) {
  const outputs = nodeDef(type).outputs
  return typeof outputs === 'function' ? outputs(config || {}) : outputs || null
}

export function visibleFields(type, config = {}) {
  return nodeDef(type).fields.filter((field) => field.section || !field.depends || field.depends(config || {}))
}

export function colorOf(type) {
  return COLORS[nodeDef(type).color] || COLORS.gray
}

export function defaultConfig(type) {
  const config = {}

  for (const field of nodeDef(type).fields) {
    if (field.key && field.default !== undefined) config[field.key] = field.default
  }

  return config
}

export function isEmpty(value) {
  if (value === undefined || value === null || value === '') return true
  if (Array.isArray(value)) return !value.length
  if (typeof value === 'object') return !Object.keys(value).length

  return false
}

export function missingFields(type, config = {}) {
  const def = nodeDef(type)
  const fields = visibleFields(type, config).filter((field) => !field.section)
  if (typeof def.required === 'function') {
    const keys = def.required(config || {})
    return fields.filter((field) => keys.includes(field.key))
  }

  return fields.filter((field) => field.required && isEmpty(config?.[field.key]))
}

function short(value, size = 28) {
  const text = String(value)

  return text.length > size ? `${text.slice(0, size - 1)}…` : text
}

export function summarize(type, config = {}) {
  const def = nodeDef(type)
  if (def.summary) {
    const text = def.summary(config || {})
    return text ? [{ label: '', value: short(text, 40) }] : []
  }
  if (def.preview) return []

  const lines = []

  for (const field of visibleFields(type, config)) {
    if (field.section) continue
    const value = config[field.key]
    if (isEmpty(value)) continue

    let text = value
    if (field.type === 'select') {
      const choices = typeof field.options === 'function' ? field.options(config) : field.options || []
      const option = choices.find((item) => (item.value ?? item) === value)
      text = option?.label ?? option ?? value
    } else if (field.type === 'keyvalue') {
      text = Object.keys(value).join(', ')
    } else if (field.type === 'instagram_posts') {
      text = value.length === 1 ? '1 post' : `${value.length} posts`
    } else if (field.type === 'list') {
      text = value.map((item) => item.value ?? item).join(', ')
    } else if (typeof value === 'object') {
      text = JSON.stringify(value)
    }

    lines.push({ label: field.label, value: short(text) })
    if (lines.length === 2) break
  }

  return lines
}

export function makeNode(type, position) {
  const def = nodeDef(type)

  return {
    id: `${type}-${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`,
    type: 'custom',
    position,
    data: { label: def.label, nodeType: type, config: defaultConfig(type) },
  }
}

const RESERVED = ['label', 'nodeType', 'config', 'type', 'description', 'icon', 'color', 'category']

function readConfig(node) {
  const data = node.data || {}
  const config =
    'config' in data ? { ...(data.config || {}) } : Object.fromEntries(Object.entries(data).filter(([key]) => !RESERVED.includes(key)))

  if (['wait', 'delay'].includes(data.nodeType || node.type) && config.duration === undefined && config.seconds !== undefined) {
    config.duration = config.seconds
    config.unit = config.unit || 'seconds'
    delete config.seconds
  }

  return config
}

export function edgeLabel(edge, source) {
  if (edge.label) return edge.label
  const output = source ? (outputsOf(source.data?.nodeType, source.data?.config) || []).find((item) => item.id === edge.sourceHandle) : null
  if (output) return output.label
  if (edge.sourceHandle === 'true') return 'Yes'
  if (edge.sourceHandle === 'false') return 'No'

  return ''
}

function defaultHandle(node) {
  const outputs = node ? outputsOf(node.data.nodeType, node.data.config) || [] : []
  return outputs.some((output) => output.id === 'done') ? 'done' : null
}

export function readGraph(json) {
  let graph = {}
  try {
    graph = typeof json === 'string' ? JSON.parse(json || '{}') : json || {}
  } catch {
    graph = {}
  }

  const nodes = (graph.nodes || []).map((node) => {
    const nodeType = node.data?.nodeType || node.type
    return {
      id: String(node.id),
      type: 'custom',
      position: { x: Number(node.position?.x) || 0, y: Number(node.position?.y) || 0 },
      data: {
        label: node.data?.label || nodeDef(nodeType).label,
        nodeType,
        config: readConfig(node),
      },
    }
  })

  const byId = Object.fromEntries(nodes.map((node) => [node.id, node]))

  const edges = (graph.edges || []).map((edge) => ({
    id: String(edge.id || `e-${edge.source}-${edge.target}`),
    source: String(edge.source),
    target: String(edge.target),
    sourceHandle: edge.sourceHandle || defaultHandle(byId[String(edge.source)]),
    targetHandle: edge.targetHandle || null,
    label: edgeLabel(edge, byId[String(edge.source)]),
    data: { condition: storedCondition(edge, byId[String(edge.source)]) },
  }))

  return { nodes, edges, viewport: graph.viewport || null }
}

function branchCondition(source, handle) {
  if (nodeDef(source?.data?.nodeType).type !== 'if_else' || source?.data?.config?.rules) return ''

  const expression = (source.data.config?.condition || '').trim()
  if (!expression) return ''
  if (handle === 'true') return expression
  if (handle === 'false') return `not (${expression})`

  return ''
}

function storedCondition(edge, source) {
  const condition = (edge.data?.condition || '').trim()

  return condition && condition === branchCondition(source, edge.sourceHandle) ? '' : condition
}

export function writeGraph(nodes, edges, viewport) {
  const byId = Object.fromEntries(nodes.map((node) => [node.id, node]))

  return {
    nodes: nodes.map((node) => ({
      id: node.id,
      type: 'custom',
      position: { x: Math.round(node.position.x), y: Math.round(node.position.y) },
      data: {
        label: node.data.label || nodeDef(node.data.nodeType).label,
        nodeType: node.data.nodeType,
        config: node.data.config || {},
      },
    })),
    edges: edges.map((edge) => {
      const condition = (edge.data?.condition || '').trim() || branchCondition(byId[edge.source], edge.sourceHandle)

      const out = {
        id: edge.id,
        source: edge.source,
        target: edge.target,
        sourceHandle: edge.sourceHandle || null,
        targetHandle: edge.targetHandle || null,
      }
      if (edge.label) out.label = edge.label
      if (condition) out.data = { condition }

      return out
    }),
    viewport: viewport || undefined,
  }
}

export function triggerTypeOf(nodes) {
  const trigger = nodes.find((node) => isTrigger(node.data?.nodeType))

  return trigger ? nodeDef(trigger.data.nodeType).triggerType || null : null
}

export function guessCategory(name, nodes) {
  const text = String(name || '').toLowerCase()

  if (['sale', 'order', 'invoice'].some((word) => text.includes(word))) return 'Sales'
  if (['support', 'ticket', 'help'].some((word) => text.includes(word))) return 'Support'
  if (['notif', 'alert', 'remind'].some((word) => text.includes(word))) return 'Notifications'
  if (['workflow', 'automation', 'process'].some((word) => text.includes(word))) return 'Workflow Automation'

  const types = nodes.map((node) => String(node.data?.nodeType || ''))
  if (types.some((type) => type.includes('whatsapp') || type.includes('email'))) return 'Notifications'

  return null
}
