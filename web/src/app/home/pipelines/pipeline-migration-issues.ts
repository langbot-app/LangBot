const issueKeys: Record<string, string> = {
  plugin_runtime_unavailable: 'runtimeUnavailable',
  migration_failed: 'executionFailed',
  plugin_missing: 'pluginRequired',
  plugin_disabled: 'pluginRequired',
  'local.context_defaults': 'contextDefaults',
  'local.model_reasoning': 'modelReasoning',
  'local.serial_tools_preserved': 'serialTools',
  'local.retrieval_defaults': 'retrievalDefaults',
  'local.box_state_reset': 'boxReset',
  'coze.persistent_history': 'persistentHistory',
  'langflow.persistent_history': 'persistentHistory',
  'langflow.tweaks_default': 'tweaksDefault',
  'dify.timeout_default': 'timeoutDefault',
  'n8n.session_ids_reset': 'historyReset',
  'weknora.session_title_changed': 'sessionTitle',
  'migration.alias_repaired': 'aliasRepaired',
  'migration.null_default': 'nullDefault',
  'migration.output_policy_copied': 'outputPolicy',
  'migration.filtered_variables': 'filteredVariables',
  'migration.history_reset': 'historyReset',
  'migration.identity_preserved': 'identityPreserved',
  'migration.new_defaults': 'newDefaults',
  'migration.legacy_sections_archived': 'legacyArchive',
  'external.state_validation_required': 'externalState',
  'runtime.plugin_version_mismatch': 'pluginVersion',
  'runtime.schema_invalid': 'schemaChanged',
  'runtime.schema_missing': 'schemaChanged',
  'extensions.runner_excluded': 'runnerExcluded',
  'local.box_template_invalid': 'boxTemplateInvalid',
  runner_schema_incompatible: 'schemaChanged',
  plugin_version_incompatible: 'pluginVersion',
  'runtime.pending_interaction': 'pendingInteraction',
};

/** Only locally reviewed codes may select localized copy. */
export function migrationIssueKey(code: string): string | undefined {
  return Object.prototype.hasOwnProperty.call(issueKeys, code)
    ? issueKeys[code]
    : undefined;
}
