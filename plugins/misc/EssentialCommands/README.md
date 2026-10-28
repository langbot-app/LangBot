# EssentialCommands

Essential commands, previously included in LangBot, provides commands below:

- `!cmd` - Show all registered command
- `!help` - Show the help of a command
- `!reset` - Reset the current session
- `!version` - Show LangBot version
- `!func` - Show all available LLM tools
- `!plugin` - Show all loaded plugins

This plugin removes some commands that were previously available in LangBot, if you need these commands, please file an issue.

## Shared runtime

This release declares `shared-runtime-v1` / `stateless-v1`: the configured
language is resolved per invocation and the plugin keeps no tenant state in
process memory. See [SHARED_RUNTIME.md](SHARED_RUNTIME.md) for the details and
the known limits. It is not a certification claim.
