<template>
  <div class="mt-1.5 flex flex-wrap items-center gap-1.5 px-0.5" @click.stop>
    <Badge v-if="message.comment_replied" theme="green" variant="subtle" size="sm" :label="__('Replied privately')" />
    <Badge
      v-if="message.comment_hidden"
      theme="gray"
      variant="subtle"
      size="sm"
      :label="message.comment_auto_hidden ? __('Hidden by AI') : __('Hidden')"
    />
    <Button
      v-if="canReplyPrivately"
      size="sm"
      variant="subtle"
      icon-left="lucide-send"
      :label="__('Reply privately')"
      @click="open('private')"
    />
    <Button size="sm" variant="ghost" icon-left="lucide-reply" :label="__('Reply publicly')" @click="open('public')" />
    <Button
      size="sm"
      variant="ghost"
      :icon-left="message.comment_hidden ? 'lucide-eye' : 'lucide-eye-off'"
      :label="message.comment_hidden ? __('Unhide') : __('Hide')"
      :loading="hiding"
      @click="toggleHidden"
    />

    <ResponsiveDialog v-model:open="dialog" :title="__(copy.title)" size="md">
      <template #default>
        <p class="mb-3 text-sm text-ink-gray-6">{{ __(copy.help).format(REPLY_DAYS) }}</p>
        <FormControl v-model="text" type="textarea" :rows="4" :placeholder="__(copy.placeholder)" />
        <ErrorMessage :message="error" class="mt-2" />
      </template>
      <template #actions>
        <Button variant="solid" class="w-full" :loading="sending" :disabled="!text.trim()" :label="__('Send')" @click="send" />
      </template>
    </ResponsiveDialog>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Badge, Button, ErrorMessage, FormControl, call, dayjs, toast } from 'frappe-ui'
import ResponsiveDialog from '@/components/Common/ResponsiveDialog.vue'
import { REPLY_DAYS, REPLY_MODES } from '@/data/instagram'
import { errorMessage } from '@/utils/format'
import { translate as __ } from '@/translation'

const props = defineProps({
  message: { type: Object, required: true },
})

const emit = defineEmits(['changed'])

const dialog = ref(false)
const mode = ref('private')
const text = ref('')
const error = ref('')
const sending = ref(false)
const hiding = ref(false)

const copy = computed(() => REPLY_MODES[mode.value])

const canReplyPrivately = computed(
  () => !props.message.comment_replied && dayjs(props.message.creation).isAfter(dayjs().subtract(REPLY_DAYS, 'day')),
)

function open(kind) {
  mode.value = kind
  text.value = ''
  error.value = ''
  dialog.value = true
}

async function send() {
  sending.value = true
  error.value = ''
  try {
    const method = mode.value === 'private' ? 'reply_privately' : 'reply_publicly'
    await call(`onechat.instagram.comments.${method}`, { message: props.message.name, text: text.value })
    if (mode.value === 'private') props.message.comment_replied = 1
    dialog.value = false
    toast.success(mode.value === 'private' ? __('Private reply sent') : __('Reply posted'))
    emit('changed')
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    sending.value = false
  }
}

async function toggleHidden() {
  hiding.value = true
  try {
    const result = await call('onechat.instagram.comments.set_hidden', {
      message: props.message.name,
      hidden: props.message.comment_hidden ? 0 : 1,
    })
    props.message.comment_hidden = result.hidden
    props.message.comment_auto_hidden = 0
    emit('changed')
  } catch (err) {
    toast.error(errorMessage(err))
  } finally {
    hiding.value = false
  }
}
</script>
