# ChatGPT / Codex subscription

LangBot's **OpenAI Codex** model provider uses **Sign in with ChatGPT** and the account's Codex entitlement. It is separate from the existing OpenAI API-key provider: subscribing to ChatGPT does not supply an OpenAI Platform API key, and API-key billing is unchanged.

## Connect an account

1. Open **Models**, choose **Add Provider**, and select **OpenAI Codex**.
2. Enter a provider name and choose **Save and sign in**. This saves the provider before authorization, so an interrupted login can be retried from its settings.
3. Open the OpenAI authorization link and enter the one-time code displayed in LangBot. Sign in on OpenAI's site, not in LangBot.
4. If OpenAI asks you to enable device-code authorization, enable it in your ChatGPT account's security settings, or contact your workspace administrator.
5. Keep the LangBot dialog open until it confirms the connection, then finish the form.
6. Use the existing **Scan models** or **Add model** controls, test the model, and select it in a pipeline as usual. Only LLM models are supported by this provider.

The device-code flow also works when LangBot runs remotely or in Docker: the browser does not need to reach a localhost OAuth callback on the server. Serve the LangBot management panel over HTTPS when accessing it remotely.

The account's model catalog is authoritative. A model listed elsewhere or entered manually is not a guarantee that this account has access. Scan errors are reported rather than replaced with a fabricated available-model list.

## Reconnect and disconnect

Open the provider's existing settings to sign in again or disconnect. LangBot refreshes expiring access tokens automatically. A revoked or invalid refresh grant requires another sign-in; transient network failures are not proof that the grant was revoked.

**Disconnect** removes this provider's locally stored authorization. It does not log the account out of other applications or revoke the account globally. Canceling a pending sign-in is separate from disconnecting an existing account. Removing a provider also removes its authorization; the normal rule that models must be removed first still applies.

A saved provider can remain disconnected. Scanning or invoking it then returns a sign-in-required error; LangBot does not silently switch to paid API-key billing.

## Usage and deployment boundary

Calls consume the connected account's included Codex usage and remain subject to OpenAI's plan limits, model availability, workspace policies, and terms. Token counts recorded by LangBot are request usage, not a measurement of remaining subscription quota or an OpenAI invoice.

Use this integration for your own authorized account and trusted workflows. Third-party sign-in support is not permission to pool accounts, resell subscription quota, or redistribute one subscription as a shared API service. For a public or commercial multi-user service, use the appropriate OpenAI API or separately authorized enterprise arrangement. The provider remains a Workspace resource in LangBot: consider who can invoke its models before connecting a personal account.

## Credential handling and API surface

- OAuth credentials are stored server-side separately from provider API keys. Provider and model reads do not supply OAuth access, refresh, or ID tokens.
- Authorization uses a fixed OpenAI origin. The Codex provider does not accept a custom base URL or manually supplied API keys.
- Authentication controls require an authenticated LangBot browser user with `provider_secret.manage` in the selected Workspace. Pending attempts are scoped to the Workspace, provider, and initiating user.
- Browser storage must not contain OAuth tokens. Treat the server database and its backups as sensitive application data.
- MCP and LangBot API keys do not expose the browser-only OAuth controls. Agents may inspect configured providers and models with the existing tools, but a human connects the subscription in the management panel.

The provider-scoped authentication routes are under `/api/v1/provider/providers/{uuid}/codex`:

| Method | Suffix | Purpose |
| --- | --- | --- |
| GET | `/status` | Read local connection state without returning credentials |
| POST | `/device` | Start device authorization |
| POST | `/device/poll` | Poll the initiating user's authorization attempt |
| DELETE | `/device/{authorization_id}` | Cancel only that pending attempt |
| DELETE | `/auth` | Remove local authorization |

Use the returned polling interval and expiration time. An expired attempt must be restarted. These routes are not a general-purpose subscription-to-API gateway.

## References

- [OpenAI Codex authentication](https://developers.openai.com/codex/auth): ChatGPT versus API-key access and device-code login.
- [Hermes Agent providers](https://hermes-agent.nousresearch.com/docs/integrations/providers/): subscription device authentication and refresh recovery.
- [OpenClaw OpenAI provider](https://docs.openclaw.ai/providers/openai): subscription and API-key route distinctions.
- [New API](https://github.com/QuantumNous/new-api): reference for Codex protocol compatibility; its gateway/account-pooling product model is not adopted here.

## 中文快速说明

在「模型」中添加提供商，选择 **OpenAI Codex**，填写名称并点击「保存并登录」。打开 OpenAI 授权页面，输入 LangBot 显示的一次性验证码，完成授权后回到原对话框。随后照常扫描或添加模型、测试模型，并在流水线中选择它。

无需填写 API Key，也无需为远程服务器配置 localhost 回调。登录中断后可以从该提供商的设置中重试；断开连接只删除 LangBot 中保存的授权。调用消耗所登录账号的 Codex 额度，受账号实际权限和 OpenAI 限制约束，不会自动转用按量付费的 OpenAI API。

此功能用于自己的授权账号及可信工作流，不应将个人订阅作为面向多个用户转售或共享的 API 服务。提供商仍是 LangBot 工作空间内的资源，连接个人账号前请确认模型的使用范围。
