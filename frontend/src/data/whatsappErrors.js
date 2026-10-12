export const WHATSAPP_ERRORS = {
  130472: {
    meaning: 'Meta held this marketing message back as part of an experiment on the customer’s number.',
    action: 'Nothing to do. You are not charged for these.',
  },
  131000: {
    meaning: 'WhatsApp had an unknown error while sending.',
    action: 'Retry later. If it keeps happening, check the account health in Settings → WhatsApp accounts.',
  },
  131008: { meaning: 'A required value in the message was missing.', action: 'Fill every variable of the template before sending.' },
  131009: {
    meaning: 'A value in the message is not valid. For products, the item is usually not in the WhatsApp catalog or not approved yet.',
    action:
      'Check the template variables, links and phone number. For products, sync the item to the catalog and wait for Meta to approve it.',
  },
  131021: { meaning: 'The message was sent to your own business number.', action: 'Use the customer’s number instead.' },
  131026: {
    meaning:
      'The message could not be delivered. The number may not be on WhatsApp, the app may be very old, or the customer has not accepted WhatsApp’s latest terms.',
    action: 'Check the number is correct and on WhatsApp. Ask the customer to update WhatsApp.',
  },
  131031: { meaning: 'Your WhatsApp Business account is locked.', action: 'Open Meta Business Manager and resolve the account issue.' },
  131042: {
    meaning: 'There is a payment problem on your WhatsApp Business account.',
    action: 'Add or fix the payment method in Meta Business Manager.',
  },
  131045: {
    meaning: 'The sending number is not registered correctly.',
    action: 'Re-register the number in Meta, then test the connection.',
  },
  131047: {
    meaning: 'More than 24 hours passed since the customer last wrote, so free-form messages are blocked.',
    action: 'Send an approved template instead. The chat opens again once they reply.',
  },
  131048: {
    meaning: 'Too many of your messages were blocked or reported, so WhatsApp slowed you down.',
    action: 'Send fewer messages and improve template quality.',
  },
  131049: {
    meaning: 'Meta limits how many marketing messages each person receives, to keep engagement healthy.',
    action: 'Send marketing messages to this person less often, try again later, or use a utility template when it fits.',
  },
  131050: {
    meaning: 'The customer stopped marketing messages from your business.',
    action: 'Don’t send marketing templates to this person.',
  },
  131051: { meaning: 'This message type is not supported.', action: 'Send it as text, a template or a supported media type.' },
  131052: { meaning: 'The customer’s media could not be downloaded.', action: 'Ask the customer to send the file again.' },
  131053: {
    meaning: 'The media file could not be uploaded or processed.',
    action: 'Check the file type and size, and that the file link opens without a login.',
  },
  131056: {
    meaning: 'Too many messages went to the same number in a short time.',
    action: 'Wait a little before messaging this person again.',
  },
  132000: { meaning: 'The number of template values does not match the template.', action: 'Fill exactly the variables the template has.' },
  132001: {
    meaning: 'The template does not exist in this language, or it is not approved.',
    action: 'Sync templates from Meta and check the template language.',
  },
  132005: { meaning: 'The template text became too long after filling the variables.', action: 'Use shorter values.' },
  132007: { meaning: 'The template text breaks WhatsApp’s content policy.', action: 'Edit the template and submit it again.' },
  132012: {
    meaning: 'A template value has the wrong format.',
    action: 'Match the format the template expects, for example a date or currency.',
  },
  132015: { meaning: 'The template is paused because of low quality.', action: 'Improve the template or use another one.' },
  132016: { meaning: 'The template is disabled because of low quality.', action: 'Create a new template with better content.' },
  133010: {
    meaning: 'The sending number is not registered on WhatsApp.',
    action: 'Register the number in Meta, then test the connection.',
  },
  368: {
    meaning: 'Your account is temporarily blocked for a policy violation.',
    action: 'Check Account quality in Meta Business Manager.',
  },
}

export const NO_REASON = {
  meaning:
    'WhatsApp did not return a reason. Often the message was stopped before reaching WhatsApp, for example an invalid number or a missing template value.',
  action: 'Open the Delivery report for the broadcast and check the number and template values.',
}

const PHRASES = [
  [/healthy ecosystem/i, 131049],
  [/part of an experiment/i, 130472],
  [/re-?engagement/i, 131047],
  [/undeliverable/i, 131026],
  [/pair rate limit/i, 131056],
  [/spam rate limit/i, 131048],
  [/media upload/i, 131053],
]

export function errorCode(text) {
  const value = String(text || '')
  const match = value.match(/\((\d{3,6})\)/) || value.match(/\b(1[3-9]\d{4}|368)\b/)
  if (match) return Number(match[1])
  return PHRASES.find(([pattern]) => pattern.test(value))?.[1] || null
}

export function explainError(text) {
  if (!text) return NO_REASON
  const code = errorCode(text)
  return (code && WHATSAPP_ERRORS[code]) || null
}

const AUTOMATION = [
  [
    /no phone number to send to|needs a conversation/i,
    'The flow reached a messaging step but had no WhatsApp contact to send to.',
    'Start the flow from a WhatsApp message, or set the phone field on the trigger.',
  ],
  [
    /stopped after \d+ steps/i,
    'The flow went round in a loop and was stopped to protect your account.',
    'Add a question or a wait inside the loop, or end it with a condition.',
  ],
  [/has no trigger|add a trigger/i, 'The flow has no trigger, so it cannot run.', 'Open the flow and add a trigger.'],
  [
    /^(\w+\.)*\w*:?\s*(pick|write|name|list|add at least)\b/i,
    'A step in the flow is missing a setting.',
    'Open the flow in the builder and fill in the step it points to.',
  ],
  [
    /payment (link|gateway)|nothing is due|to collect payment/i,
    'The payment step could not create a payment request.',
    'Set up a default Payment Gateway Account in ERPNext, and check the invoice or order belongs to the customer and is still unpaid.',
  ],
  [
    /permission|not permitted/i,
    'The flow tried to read or change a record it has no access to.',
    'Give the flow’s user the role it needs, or change the step to a record it can use.',
  ],
  [
    /mandatory|value missing/i,
    'A record the flow creates or updates is missing a required field.',
    'Fill the required fields in the Create or Update step.',
  ],
  [
    /does ?not ?exist|not found|could not find/i,
    'A record the flow used was deleted or renamed.',
    'Point the step to a record that exists.',
  ],
  [
    /could not reach|timed out|connection|refused the (sign-in|api key)/i,
    'The connected site (ERPNext or Frappe CRM) could not be reached, or it refused OneChat’s sign-in.',
    'Test the connection in Settings → Integrations and sign in again if needed.',
  ],
]

export const AUTOMATION_UNKNOWN = {
  meaning: 'The flow hit an error it could not recover from.',
  action: 'Open the flow and check its recent runs to see which step failed.',
}

export function explainAutomation(text) {
  const code = errorCode(text)
  if (code && WHATSAPP_ERRORS[code]) return { code, ...WHATSAPP_ERRORS[code] }
  const match = AUTOMATION.find(([pattern]) => pattern.test(String(text || '')))
  return match ? { meaning: match[1], action: match[2] } : AUTOMATION_UNKNOWN
}

const META_API = [
  [
    [100],
    'Meta rejected the request. Usually the WhatsApp Business Account ID is wrong, or the dates are older than Meta keeps.',
    'Check the Business Account ID in Settings → WhatsApp. Meta keeps about a year of cost data.',
  ],
  [
    [190],
    'The access token has expired or was revoked.',
    'Generate a new token in Meta Business Settings and paste it in Settings → WhatsApp.',
  ],
  [
    [3, 10, 200],
    'The access token is missing a permission this needs.',
    'Generate a token with whatsapp_business_management and whatsapp_business_messaging, then paste it in Settings → WhatsApp.',
  ],
  [[4, 17, 32, 613, 80007, 80008], 'Meta is limiting how often OneChat can ask for data.', 'Wait a few minutes and sync again.'],
  [
    [1, 2],
    'Meta had a temporary problem or does not support this for the account.',
    'Try again later. If it keeps happening, check the account in WhatsApp Manager.',
  ],
]

export const META_UNKNOWN = {
  meaning: 'Meta returned an error while syncing.',
  action: 'Sync again later. If it keeps failing, test the account in Settings → WhatsApp.',
}

export function explainMeta(text) {
  const value = String(text || '')
  const code = Number((value.match(/\(#(\d+)\)/) || [])[1]) || errorCode(value)
  if (code && WHATSAPP_ERRORS[code]) return { code, ...WHATSAPP_ERRORS[code] }
  const match = code && META_API.find(([codes]) => codes.includes(code))
  if (match) return { code, meaning: match[1], action: match[2] }
  if (/invalid parameter/i.test(value)) return { meaning: META_API[0][1], action: META_API[0][2] }
  if (/permission/i.test(value)) return { meaning: META_API[2][1], action: META_API[2][2] }
  if (/access token/i.test(value)) return { meaning: META_API[1][1], action: META_API[1][2] }
  return { code: code || null, ...META_UNKNOWN }
}

export const OUTCOME_HINTS = {
  Stopped: {
    meaning: 'An agent took over, the customer asked to stop, or someone stopped the run.',
    action: 'Normal when agents step in. If many runs stop at the same step, check that step’s wording.',
  },
  Expired: {
    meaning: 'The customer did not reply before the wait time ran out.',
    action: 'Ask a shorter question, offer buttons, or give more time in the flow’s Behaviour settings.',
  },
  Failed: {
    meaning: 'The step raised an error and the run ended.',
    action: 'See Failed runs for the error, then fix the step in the flow builder.',
  },
  Waiting: {
    meaning: 'The run is still waiting for the customer to reply.',
    action: 'Nothing to do yet. It moves on when they answer or the wait time ends.',
  },
}
