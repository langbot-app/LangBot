import { useTranslation } from 'react-i18next';
import { Bot as BotIcon, Route } from 'lucide-react';
import type { Agent, EventBinding } from '@/app/infra/entities/api';
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectSeparator,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { isMessageRoute, routeKey, routeLabel } from './message-policy';

export const BOT_SCOPE = 'bot';

/** Pick what is being edited: the bot default or one message route's override. */
export default function PolicyScopeSelect({
  value,
  onChange,
  bindings,
  agents,
  isCustom,
}: {
  value: string;
  onChange: (value: string) => void;
  bindings: EventBinding[];
  agents: Agent[];
  /** Whether a route overrides what is being edited, for its marker. */
  isCustom: (binding: EventBinding) => boolean;
}) {
  const { t } = useTranslation();
  const routes = bindings
    .map((binding, index) => ({ binding, index }))
    .filter(({ binding }) => isMessageRoute(binding));

  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-sm text-muted-foreground">
        {t('bots.policy.scopeLabel')}
      </span>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger
          className="h-8 w-[min(100%,20rem)]"
          aria-label={t('bots.policy.scopeLabel')}
        >
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={BOT_SCOPE}>
            <BotIcon className="size-4" />
            {t('bots.policy.botDefault')}
          </SelectItem>
          {routes.length > 0 && (
            <>
              <SelectSeparator />
              <SelectGroup>
                <SelectLabel>{t('bots.policy.routes')}</SelectLabel>
                {routes.map(({ binding, index }) => (
                  <SelectItem
                    key={routeKey(binding, index)}
                    value={routeKey(binding, index)}
                  >
                    <Route className="size-4" />
                    <span className="truncate">
                      {routeLabel(binding, index, agents)}
                    </span>
                    <span className="ml-1 text-xs text-muted-foreground">
                      {isCustom(binding)
                        ? t('bots.policy.custom')
                        : t('bots.policy.inherit')}
                    </span>
                  </SelectItem>
                ))}
              </SelectGroup>
            </>
          )}
        </SelectContent>
      </Select>
    </div>
  );
}
