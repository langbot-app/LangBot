import { useTranslation } from 'react-i18next';
import { AlertCircle, X } from 'lucide-react';
import { useState, useEffect } from 'react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { backendClient } from '@/app/infra/http';

export function BetaBanner() {
  const { t, i18n } = useTranslation();
  const [show, setShow] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    const checkBetaStatus = async () => {
      try {
        const info = await backendClient.getSystemInfo();
        const shouldShow =
          info.deployment_mode === 'cloud' && info.beta === true;
        setShow(shouldShow);
      } catch {
        setShow(false);
      }
    };

    checkBetaStatus();
  }, []);

  if (!show || dismissed) {
    return null;
  }

  const cloudUrl =
    i18n.language === 'zh-Hans' || i18n.language === 'zh_CN'
      ? 'https://langbot.app/zh/cloud'
      : i18n.language === 'ja' || i18n.language === 'ja_JP'
        ? 'https://langbot.app/ja/cloud'
        : 'https://langbot.app/cloud';

  const ossUrl =
    i18n.language === 'zh-Hans' || i18n.language === 'zh_CN'
      ? 'https://langbot.app/zh/docs/quick-start/deploy'
      : i18n.language === 'ja' || i18n.language === 'ja_JP'
        ? 'https://langbot.app/ja/docs/quick-start/deploy'
        : 'https://langbot.app/docs/quick-start/deploy';

  return (
    <Alert className="rounded-none border-x-0 border-t-0 bg-amber-50 dark:bg-amber-950/20 border-amber-200 dark:border-amber-900/50 py-2">
      <div className="flex items-start gap-3">
        <AlertCircle className="h-4 w-4 mt-0.5 text-amber-600 dark:text-amber-500 shrink-0" />
        <AlertDescription className="text-sm text-amber-900 dark:text-amber-100 flex-1">
          {t('beta_banner.message')}{' '}
          <a
            href={cloudUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="underline hover:text-amber-700 dark:hover:text-amber-300 font-medium"
          >
            {t('beta_banner.cloud_link')}
          </a>{' '}
          {t('beta_banner.or')}{' '}
          <a
            href={ossUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="underline hover:text-amber-700 dark:hover:text-amber-300 font-medium"
          >
            {t('beta_banner.oss_link')}
          </a>
          {t('beta_banner.period')}
        </AlertDescription>
        <button
          onClick={() => setDismissed(true)}
          className="shrink-0 text-amber-600 dark:text-amber-500 hover:text-amber-800 dark:hover:text-amber-300 p-1 -mt-1 -mr-2"
          aria-label={t('beta_banner.dismiss')}
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </Alert>
  );
}
