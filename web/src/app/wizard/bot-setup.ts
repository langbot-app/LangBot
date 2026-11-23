import type { Bot } from '@/app/infra/entities/api';
import { appendMessageRoutingTemplate } from '@/app/home/bots/components/bot-form/message-routing-template';

export interface WizardDraft {
  adapter: string;
  botUuid: string | null;
  pipelineUuid: string | null;
}

interface SetupClient {
  getBot(uuid: string): Promise<{ bot: Bot }>;
  createBot(bot: Bot): Promise<{ uuid: string }>;
  createPipeline(pipeline: {
    name: string;
    description: string;
    config: Record<string, unknown>;
  }): Promise<{ uuid: string }>;
}

/** Keep successful resources in the draft so a retry never recreates them. */
export async function prepareWizardBot(
  client: SetupClient,
  draft: WizardDraft,
  bot: Bot,
  pipelineName: string,
) {
  if (draft.botUuid) {
    return {
      uuid: draft.botUuid,
      bot: (await client.getBot(draft.botUuid)).bot,
    };
  }
  if (!draft.pipelineUuid) {
    draft.pipelineUuid = (
      await client.createPipeline({
        name: pipelineName,
        description: bot.description ?? '',
        config: {},
      })
    ).uuid;
  }
  const configuredBot: Bot = {
    ...bot,
    event_bindings: appendMessageRoutingTemplate([], {
      target_type: 'pipeline',
      target_uuid: draft.pipelineUuid,
    }),
  };
  const { uuid } = await client.createBot(configuredBot);
  draft.botUuid = uuid;
  return { uuid, bot: configuredBot };
}

/** Saving adapter settings must not replace or re-enable a member's routes. */
export function wizardBindingsIfMissing(bot: Bot, pipelineUuid: string) {
  return bot.event_bindings?.length
    ? {}
    : {
        event_bindings: appendMessageRoutingTemplate([], {
          target_type: 'pipeline',
          target_uuid: pipelineUuid,
        }),
      };
}
