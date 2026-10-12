export const REPLY_DAYS = 7

export const REPLY_MODES = {
  private: {
    title: 'Reply privately',
    help: 'Sent as a DM. Instagram allows one private reply per comment, within {0} days. You can message again once they reply.',
    bulkHelp: 'Each person gets this as a DM. Comments already replied to privately, or older than {0} days, are skipped.',
    placeholder: 'Hi! Here are the details…',
  },
  public: {
    title: 'Reply publicly',
    help: 'Posted under their comment, visible to everyone.',
    bulkHelp: 'Posted under each selected comment, visible to everyone.',
    placeholder: 'Sent you a DM',
  },
}

export function postImage(post) {
  return post?.thumbnail_url || post?.media_url
}
