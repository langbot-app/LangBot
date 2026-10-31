import type { TFunction } from 'i18next';
import { toast } from 'sonner';

export function showBotError(error: unknown, title: string, t: TFunction) {
  const detail =
    error && typeof error === 'object'
      ? (error as {
          code?: string;
          msg?: string;
          message?: string;
          request_id?: string;
        })
      : {};
  const message = detail.msg || detail.message || '';
  const description =
    detail.code === 'internal_error'
      ? [
          t('bots.internalErrorHint'),
          detail.request_id &&
            t('bots.errorReference', { id: detail.request_id }),
        ]
          .filter(Boolean)
          .join('\n')
      : message;
  toast.error(
    detail.code === 'bot_apply_failed'
      ? t('bots.applyFailed')
      : title.replace(/[:：]\s*$/, ''),
    { description, duration: 10000 },
  );
}
