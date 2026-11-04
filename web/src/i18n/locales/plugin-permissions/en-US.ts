export default {
  managerRequired:
    'Managing plugin permissions requires resource.manage. Only accounts can confirm grants; API keys can only revoke existing grants.',
  title: 'Plugin permissions',
  undeclared: 'Undeclared permissions',
  compatibilityWarning:
    'This plugin does not declare permissions. Confirmation grants all 16 legacy plugin API capabilities; individual grants can be revoked afterward. No workspace Application API operations are granted.',
  pending: 'Permission confirmation required',
  saved: 'Permissions saved',
  failed: 'Unable to update permissions',
  retry: 'Retry',
  revoke: 'Revoke',
  dangerous: 'Dangerous',
  sendsMessages: 'Sends bot messages',
  requires: 'Requires {{permissions}}',
  review: 'Review permissions',
  confirm: 'Confirm grants',
  confirmDescription:
    'Grant the selected permissions to this plugin installation. Dangerous permissions and bot messaging are highlighted.',
  grantInPlugin: 'Grant this operation in plugin permissions first',
};
