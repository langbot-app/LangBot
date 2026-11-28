export default {
  title: 'Webhook URLs',
  description:
    'External systems can push events to these URLs, and the plugin can then message users proactively. The URLs are public; the plugin verifies each caller.',
  disabled: 'The plugin is disabled, so requests to these URLs are rejected.',
  loadFailed: 'Failed to load webhook URLs',
  prefixHint:
    'The URL prefix comes from api.webhook_prefix; make sure external systems can reach it.',
  copy: 'Copy URL',
};
