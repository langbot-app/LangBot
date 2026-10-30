# Card Interaction Probe

Local test plugin for event-processor interactive cards. It requires a platform adapter that supports `interaction.request`.

1. Build this directory with `lbp build` and install the resulting plugin package in LangBot.
2. Create an event processor using `Card Interaction Probe / default` and bind it to a bot's `message.received` event.
3. Send `/card-probe` to the bot. The processor calls `present_interactive_card`.
4. Click either button. The same processor receives `interaction.submitted` and replies with the selected action.

The command is exact-match, so unrelated messages do not create cards.
