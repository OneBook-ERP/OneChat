export const NUMBER_TYPES = ['Int', 'Float', 'Currency', 'Percent', 'Rating', 'Duration']
export const DATE_TYPES = ['Date', 'Datetime']

const TEXT_OPERATORS = ['equals', 'not_equals', 'contains', 'not_contains', 'starts_with', 'is_one_of', 'is_empty', 'is_not_empty']
const CHOICE_OPERATORS = ['equals', 'not_equals', 'is_one_of', 'is_empty', 'is_not_empty']
const NUMBER_OPERATORS = ['equals', 'not_equals', 'greater_than', 'less_than', 'is_empty', 'is_not_empty']
const DATE_OPERATORS = ['on', 'before', 'after', 'is_today', 'is_past', 'is_future', 'is_empty', 'is_not_empty']
const CHECK_OPERATORS = ['is_checked', 'is_not_checked']

export const OPERATOR_LABELS = {
  equals: 'is',
  not_equals: 'is not',
  contains: 'contains',
  not_contains: 'does not contain',
  starts_with: 'starts with',
  is_one_of: 'is one of',
  greater_than: 'is more than',
  less_than: 'is less than',
  on: 'is on',
  before: 'is before',
  after: 'is after',
  is_today: 'is today',
  is_past: 'is in the past',
  is_future: 'is in the future',
  is_empty: 'is empty',
  is_not_empty: 'is not empty',
  is_checked: 'is ticked',
  is_not_checked: 'is not ticked',
}

export const NO_VALUE = ['is_empty', 'is_not_empty', 'is_today', 'is_past', 'is_future', 'is_checked', 'is_not_checked']

export function kindOf(fieldtype) {
  if (fieldtype === 'Check') return 'check'
  if (NUMBER_TYPES.includes(fieldtype)) return 'number'
  if (DATE_TYPES.includes(fieldtype)) return 'date'
  if (fieldtype === 'Select') return 'choice'
  if (fieldtype === 'Link') return 'link'
  return 'text'
}

export function operatorsFor(fieldtype) {
  const kind = kindOf(fieldtype)
  if (kind === 'check') return CHECK_OPERATORS
  if (kind === 'number') return NUMBER_OPERATORS
  if (kind === 'date') return DATE_OPERATORS
  if (kind === 'choice' || kind === 'link') return CHOICE_OPERATORS
  return TEXT_OPERATORS
}

function quote(value) {
  return `'${String(value ?? '')
    .replace(/\\/g, '\\\\')
    .replace(/'/g, "\\'")}'`
}

function number(value) {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? String(parsed) : '0'
}

function listOf(value) {
  return String(value || '')
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
}

function clause(rule, fieldtype) {
  const field = `doc.${rule.field}`
  const kind = kindOf(fieldtype)
  const literal = kind === 'number' ? number(rule.value) : quote(rule.value)
  const date = `frappe.utils.getdate(${field})`

  switch (rule.operator) {
    case 'equals':
      return `${field} == ${literal}`
    case 'not_equals':
      return `${field} != ${literal}`
    case 'contains':
      return `${quote(rule.value)} in (${field} or '')`
    case 'not_contains':
      return `${quote(rule.value)} not in (${field} or '')`
    case 'starts_with':
      return `(${field} or '').startswith(${quote(rule.value)})`
    case 'is_one_of':
      return `${field} in [${listOf(rule.value)
        .map(kind === 'number' ? number : quote)
        .join(', ')}]`
    case 'greater_than':
      return `(${field} or 0) > ${number(rule.value)}`
    case 'less_than':
      return `(${field} or 0) < ${number(rule.value)}`
    case 'on':
      return `${field} and ${date} == frappe.utils.getdate(${quote(rule.value)})`
    case 'before':
      return `${field} and ${date} < frappe.utils.getdate(${quote(rule.value)})`
    case 'after':
      return `${field} and ${date} > frappe.utils.getdate(${quote(rule.value)})`
    case 'is_today':
      return `${field} and ${date} == frappe.utils.getdate()`
    case 'is_past':
      return `${field} and ${date} < frappe.utils.getdate()`
    case 'is_future':
      return `${field} and ${date} > frappe.utils.getdate()`
    case 'is_empty':
      return `not ${field}`
    case 'is_not_empty':
      return `bool(${field})`
    case 'is_checked':
      return `${field} == 1`
    case 'is_not_checked':
      return `${field} != 1`
    default:
      return ''
  }
}

export function compile(condition, types = {}) {
  const parts = (condition.rules || [])
    .filter((rule) => rule.field && rule.operator)
    .map((rule) => clause(rule, types[rule.field]))
    .filter(Boolean)

  if (parts.length < 2) return parts[0] || ''
  return parts.map((part) => `(${part})`).join(condition.match === 'any' ? ' or ' : ' and ')
}

function split(text, word) {
  const out = []
  let depth = 0
  let quoteChar = ''
  let start = 0
  const token = ` ${word} `

  for (let i = 0; i < text.length; i++) {
    const char = text[i]
    if (quoteChar) {
      if (char === '\\') i++
      else if (char === quoteChar) quoteChar = ''
      continue
    }
    if (char === '"' || char === "'") quoteChar = char
    else if (char === '(' || char === '[') depth++
    else if (char === ')' || char === ']') depth--
    else if (depth === 0 && text.startsWith(token, i)) {
      out.push(text.slice(start, i))
      start = i + token.length
      i += token.length - 1
    }
  }

  out.push(text.slice(start))
  return out.map((part) => part.trim())
}

function unwrap(text) {
  let value = text.trim()
  while (value.startsWith('(') && value.endsWith(')') && balanced(value.slice(1, -1))) {
    value = value.slice(1, -1).trim()
  }
  return value
}

function balanced(text) {
  let depth = 0
  let quoteChar = ''
  for (let i = 0; i < text.length; i++) {
    const char = text[i]
    if (quoteChar) {
      if (char === '\\') i++
      else if (char === quoteChar) quoteChar = ''
      continue
    }
    if (char === '"' || char === "'") quoteChar = char
    else if (char === '(') depth++
    else if (char === ')' && --depth < 0) return false
  }
  return depth === 0
}

const STRING = String.raw`(?:'(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*")`
const NUMBER = String.raw`-?\d+(?:\.\d+)?`
const LITERAL = `(?:${STRING}|${NUMBER})`
const FIELD = String.raw`doc\.(\w+)`
const DATE = String.raw`frappe\.utils\.getdate\(doc\.(\w+)\)`

function literal(text) {
  const value = text.trim()
  if (/^['"]/.test(value)) return value.slice(1, -1).replace(/\\(.)/g, '$1')
  return value
}

const PATTERNS = [
  [new RegExp(`^${FIELD} and ${DATE} == frappe\\.utils\\.getdate\\(\\)$`), (m) => m[1] === m[2] && { field: m[1], operator: 'is_today' }],
  [new RegExp(`^${FIELD} and ${DATE} < frappe\\.utils\\.getdate\\(\\)$`), (m) => m[1] === m[2] && { field: m[1], operator: 'is_past' }],
  [new RegExp(`^${FIELD} and ${DATE} > frappe\\.utils\\.getdate\\(\\)$`), (m) => m[1] === m[2] && { field: m[1], operator: 'is_future' }],
  [
    new RegExp(`^${FIELD} and ${DATE} (==|<|>) frappe\\.utils\\.getdate\\((${STRING})\\)$`),
    (m) => m[1] === m[2] && { field: m[1], operator: { '==': 'on', '<': 'before', '>': 'after' }[m[3]], value: literal(m[4]) },
  ],
  [new RegExp(`^${FIELD} == 1$`), (m) => ({ field: m[1], operator: 'is_checked' })],
  [new RegExp(`^${FIELD} != 1$`), (m) => ({ field: m[1], operator: 'is_not_checked' })],
  [
    new RegExp(`^${FIELD} (==|!=) (${LITERAL})$`),
    (m) => ({ field: m[1], operator: m[2] === '==' ? 'equals' : 'not_equals', value: literal(m[3]) }),
  ],
  [
    new RegExp(`^\\(${FIELD} or 0\\) (>|<) (${NUMBER})$`),
    (m) => ({ field: m[1], operator: m[2] === '>' ? 'greater_than' : 'less_than', value: m[3] }),
  ],
  [
    new RegExp(`^${FIELD} (>|<) (${NUMBER})$`),
    (m) => ({ field: m[1], operator: m[2] === '>' ? 'greater_than' : 'less_than', value: m[3] }),
  ],
  [
    new RegExp(`^(${STRING}) (in|not in) \\(${FIELD} or ''\\)$`),
    (m) => ({ field: m[3], operator: m[2] === 'in' ? 'contains' : 'not_contains', value: literal(m[1]) }),
  ],
  [
    new RegExp(`^(${STRING}) (in|not in) ${FIELD}$`),
    (m) => ({ field: m[3], operator: m[2] === 'in' ? 'contains' : 'not_contains', value: literal(m[1]) }),
  ],
  [
    new RegExp(`^\\(${FIELD} or ''\\)\\.startswith\\((${STRING})\\)$`),
    (m) => ({ field: m[1], operator: 'starts_with', value: literal(m[2]) }),
  ],
  [
    new RegExp(`^${FIELD} in \\[((?:\\s*${LITERAL}\\s*,?)*)\\]$`),
    (m) => ({ field: m[1], operator: 'is_one_of', value: (m[2].match(new RegExp(LITERAL, 'g')) || []).map(literal).join(', ') }),
  ],
  [new RegExp(`^not ${FIELD}$`), (m) => ({ field: m[1], operator: 'is_empty' })],
  [new RegExp(`^bool\\(${FIELD}\\)$`), (m) => ({ field: m[1], operator: 'is_not_empty' })],
  [new RegExp(`^${FIELD}$`), (m) => ({ field: m[1], operator: 'is_not_empty' })],
]

function parseClause(text) {
  const value = unwrap(text)
  for (const [pattern, build] of PATTERNS) {
    const match = value.match(pattern)
    if (!match) continue
    const rule = build(match)
    if (rule) return { value: '', ...rule }
  }
  return null
}

export function parse(expression) {
  const text = unwrap(String(expression || '').replace(/\s+/g, ' '))
  if (!text) return { match: 'all', rules: [] }

  const single = parseClause(text)
  if (single) return { match: 'all', rules: [single] }

  const ors = split(text, 'or')
  const ands = split(text, 'and')
  if (ors.length > 1 && ands.length > 1) return null

  const match = ors.length > 1 ? 'any' : 'all'
  const rules = (ors.length > 1 ? ors : ands).map(parseClause)
  return rules.every(Boolean) ? { match, rules } : null
}

export function describe(expression, labelOf, translate) {
  const parsed = parse(expression)
  if (!parsed?.rules.length) return ''

  const parts = parsed.rules.map((rule) => {
    const text = `${labelOf(rule.field)} ${translate(OPERATOR_LABELS[rule.operator])}`
    return NO_VALUE.includes(rule.operator) ? text : `${text} ${rule.value}`
  })
  return parts.join(` ${translate(parsed.match === 'any' ? 'or' : 'and')} `)
}
