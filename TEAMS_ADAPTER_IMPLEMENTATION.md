# Microsoft Teams Adapter Implementation

## Overview

A new Microsoft Teams platform adapter has been added to LangBot, enabling support for both personal chats and channel/group chats on Microsoft Teams.

## Files Created/Modified

### New Files

1. **`src/langbot/pkg/platform/sources/teams.py`** - Main adapter implementation
   - `TeamsMessageConverter`: Converts between LangBot message format and Teams Activity format
   - `TeamsEventConverter`: Converts between Teams Activity events and LangBot platform events
   - `TeamsAdapter`: Main adapter class with webhook handling

2. **`src/langbot/pkg/platform/sources/teams.yaml`** - Adapter manifest
   - Defines adapter metadata, configuration schema, and execution details
   - Configuration fields: `app_id` and `app_password`

### Modified Files

1. **`pyproject.toml`** - Added dependencies:
   - `botbuilder-core>=4.15.0`
   - `botbuilder-schema>=4.15.0`
   - `botframework-connector>=4.15.0`
   - Added "teams" keyword

## Features

### Supported Message Types

- ✅ Plain text messages
- ✅ Image attachments (base64, URL, and file path)
- ✅ @mentions (converted to At components)
- ✅ Message replies with quote support

### Supported Chat Types

- ✅ Personal chats (1-on-1 conversations)
- ✅ Channel chats (group/team conversations)

### Message Handling

- **Incoming Messages**: Received via webhook at the unified webhook endpoint
- **Outgoing Messages**: Sent via Bot Framework SDK using conversation references
- **Event Types**: FriendMessage (personal) and GroupMessage (channel/group)

## Configuration Requirements

### Azure Setup

1. **Register an Azure AD Application**:
   - Go to Azure Portal → Azure Active Directory → App registrations
   - Create a new registration
   - Note the **Application (client) ID** - this is your `app_id`
   - Create a **Client Secret** - this is your `app_password`

2. **Create Azure Bot Resource**:
   - Go to Azure Portal → Create a resource → Azure Bot
   - Link it to your Azure AD application
   - Enable the Microsoft Teams channel
   - Set the messaging endpoint to: `https://<your-domain>/bots/<bot-uuid>`

### LangBot Configuration

When creating a Teams bot in LangBot, provide:

```yaml
adapter: teams
adapter_config:
  app_id: "<your-microsoft-app-id>"
  app_password: "<your-microsoft-app-password>"
```

## Architecture

### Webhook Mode

The Teams adapter operates in webhook mode, similar to the Slack adapter:
- Integrates with LangBot's unified webhook system
- Receives messages at `/bots/<bot-uuid>` endpoint
- No independent server process required

### Message Flow

1. **Incoming**:
   - Teams → Azure Bot Service → LangBot Webhook
   - Bot Framework validates the request
   - Activity converted to LangBot event format
   - Event dispatched to registered listeners

2. **Outgoing**:
   - LangBot message chain → Teams Activity format
   - Reply sent via Bot Framework adapter
   - Uses conversation reference for proper routing

## Authentication

- Uses Bot Framework authentication with Microsoft App credentials
- JWT token validation handled by `BotFrameworkAdapter`
- Authorization header validated on each incoming request

## Limitations & Notes

1. **Direct Send**: The `send_message` method is limited - use `reply_message` for best results
2. **Conversation References**: The adapter uses conversation references from incoming activities to send replies
3. **Image Handling**: Images are converted to inline attachments using data URIs
4. **Streaming**: Streaming replies are not yet implemented

## Testing

To test the adapter:

1. Install dependencies: `uv sync`
2. Verify adapter initialization: `uv run python -c "from src.langbot.pkg.platform.sources.teams import TeamsAdapter; print('OK')"`
3. Configure a Teams bot in LangBot with your Azure credentials
4. Expose the LangBot API endpoint publicly (use ngrok or similar)
5. Set the messaging endpoint in Azure Bot Service
6. Add the bot to Teams and start chatting

## Troubleshooting

### Pydantic Validation Error on Initialization

**Fixed**: The adapter was updated to properly handle optional fields (`adapter`, `app`, `bot_uuid`) by:
- Setting `default=None` in pydantic.Field definitions
- Not passing these fields to `super().__init__()`
- Setting the adapter instance after parent class initialization

This resolves the validation error: "Input should be an instance of Quart" / "Input should be a valid string"

## Future Enhancements

Potential improvements:
- Adaptive Cards support
- Rich message formatting (markdown, cards)
- File attachments (non-image)
- Streaming message support
- Proactive messaging
- Team/channel member list retrieval
- Reaction handling

## Dependencies

The following Python packages were added:
- `botbuilder-core` - Core Bot Framework functionality
- `botbuilder-schema` - Activity and entity schemas
- `botframework-connector` - Bot Framework connector for authentication

## References

- [Microsoft Teams Bot Framework Documentation](https://learn.microsoft.com/en-us/microsoftteams/platform/bots/bot-features)
- [Bot Framework SDK for Python](https://github.com/microsoft/botbuilder-python)
- [Teams Conversation Bot Sample](https://learn.microsoft.com/en-us/samples/officedev/microsoft-teams-samples/officedev-microsoft-teams-samples-bot-conversation-python/)

## Sources

Research sources consulted during implementation:
- [Create an Incoming Webhook - Teams | Microsoft Learn](https://learn.microsoft.com/en-us/microsoftteams/platform/webhooks-and-connectors/how-to/add-incoming-webhook)
- [Teams Conversation Bot - Code Samples | Microsoft Learn](https://learn.microsoft.com/en-us/samples/officedev/microsoft-teams-samples/officedev-microsoft-teams-samples-bot-conversation-python/)
- [GitHub - microsoft/botbuilder-python](https://github.com/microsoft/botbuilder-python)
- [Tools and Bot Framework SDKs for Bots - Teams](https://learn.microsoft.com/en-us/microsoftteams/platform/bots/bot-features)
