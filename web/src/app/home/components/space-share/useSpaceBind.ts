import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { httpClient } from '@/app/infra/http/HttpClient';
import { rememberSpaceBindReturnPath } from '@/app/infra/space-bind-return';

/** Start the LangBot Account bind flow and return to the current page. */
export function useSpaceBind() {
  const { t } = useTranslation();
  const [binding, setBinding] = useState(false);
  const bind = async () => {
    setBinding(true);
    try {
      rememberSpaceBindReturnPath(
        `${window.location.pathname}${window.location.search}`,
      );
      const response = await httpClient.getSpaceBindAuthorizeUrl(
        `${window.location.origin}/auth/space/callback?mode=bind`,
      );
      window.location.href = response.authorize_url;
    } catch {
      toast.error(t('common.spaceLoginFailed'));
      setBinding(false);
    }
  };
  return { bind, binding };
}
