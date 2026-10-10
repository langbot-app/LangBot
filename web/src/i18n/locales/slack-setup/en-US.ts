export default {
  permissionsHint:
    'Requests message, channel, user, file and reaction permissions. Subscribes to edits/deletions, reactions, membership, channel updates, App Home and app lifecycle events; enables button/form callbacks. Channel replies still require an @mention. Existing apps need updated subscriptions and reinstallation after adding scopes.',
  title: 'Quick Slack setup',
  description:
    'Create and configure a Slack app, authorize installation, then fill the adapter credentials.',
  saveFirst: 'Create the bot draft first, then open this assistant.',
  generate: 'Generate App Configuration Tokens',
  name: 'App name',
  redirect: 'OAuth return URL',
  webhook: 'Webhook URL',
  redirectHint:
    'Only your browser needs to reach this URL. HTTPS or http://localhost is supported; no public event webhook is needed.',
  webhookHint: 'Use your public HTTPS URL and keep the /bots/… path unchanged.',
  create: 'Create and configure',
  creating: 'Creating and configuring the app…',
  authorizing: 'Completing authorization…',
  waiting:
    'The app is configured. Authorize its installation in Slack, then return here.',
  authorize: 'Authorize in Slack',
  appTokenHint:
    'Socket Mode also needs an App-Level Token. In Basic Information → App-Level Tokens, generate a token with connections:write and paste it below.',
  openApp: 'Open app settings',
  failed: 'Setup failed:',
  appCreated:
    'An app has already been created. Retrying creates another app; you can manage the existing one in Slack:',
  retry: 'Start a new setup',
  success:
    'Authorization completed. Apply the credentials below, then save the bot configuration.',
  apply: 'Fill adapter configuration',
};
