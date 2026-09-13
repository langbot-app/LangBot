/** Unavailability takes priority over the deployment's scope restriction. */
export function getBoxScopeContext(
  boxAvailable: boolean,
  forcedTemplate?: string,
) {
  forcedTemplate = forcedTemplate?.trim();
  return {
    box_available: boxAvailable,
    box_scope_editable: boxAvailable && !forcedTemplate,
    // Only expose forced-scope reasons when the sandbox is available.
    box_scope_forced: boxAvailable && !!forcedTemplate,
    box_scope_forced_global: boxAvailable && forcedTemplate === '{global}',
  };
}
