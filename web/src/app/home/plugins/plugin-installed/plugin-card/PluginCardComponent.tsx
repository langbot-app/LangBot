import { PluginCardVO } from '@/app/home/plugins/plugin-installed/PluginCardVO';
import { useState } from 'react';
import { httpClient } from '@/app/infra/http/HttpClient';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';

export default function PluginCardComponent({
  cardVO,
  onCardClick,
}: {
  cardVO: PluginCardVO;
  onCardClick: () => void;
}) {
  const { t } = useTranslation();
  const [enabled, setEnabled] = useState(cardVO.enabled);
  const [switchEnable, setSwitchEnable] = useState(true);

  function handleEnable(e: React.MouseEvent) {
    e.stopPropagation(); // 阻止事件冒泡
    setSwitchEnable(false);
    httpClient
      .togglePlugin(cardVO.author, cardVO.name, !enabled)
      .then(() => {
        setEnabled(!enabled);
      })
      .catch((err) => {
        toast.error(t('plugins.modifyFailed') + err.message);
      })
      .finally(() => {
        setSwitchEnable(true);
      });
  }
  return (
    <div
      className="w-[100%] h-[10rem] bg-white rounded-[10px] shadow-[0px_2px_2px_0_rgba(0,0,0,0.2)] p-[1.2rem] cursor-pointer"
      onClick={onCardClick}
    >
      <div className="w-full h-full flex flex-row items-start justify-start gap-[1.2rem]">
        <svg
          className="w-16 h-16 text-[#2288ee]"
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="currentColor"
        >
          <path d="M8 4C8 2.34315 9.34315 1 11 1C12.6569 1 14 2.34315 14 4C14 4.35064 13.9398 4.68722 13.8293 5H18C18.5523 5 19 5.44772 19 6V10.1707C19.3128 10.0602 19.6494 10 20 10C21.6569 10 23 11.3431 23 13C23 14.6569 21.6569 16 20 16C19.6494 16 19.3128 15.9398 19 15.8293V20C19 20.5523 18.5523 21 18 21H4C3.44772 21 3 20.5523 3 20V6C3 5.44772 3.44772 5 4 5H8.17071C8.06015 4.68722 8 4.35064 8 4Z"></path>
        </svg>

        <div className="w-full h-full flex flex-col items-start justify-between gap-[0.6rem]">
          <div className="flex flex-col items-start justify-start">
            <div className="flex flex-col items-start justify-start">
              <div className="text-[0.7rem] text-[#666]">
                {cardVO.author} /{' '}
              </div>
              <div className="flex flex-row items-center justify-start gap-[0.4rem]">
                <div className="text-[1.2rem] text-black">{cardVO.name}</div>
                <Badge variant="outline" className="text-[0.7rem]">
                  v{cardVO.version}
                </Badge>
              </div>
            </div>

            <div className="text-[0.8rem] text-[#666] line-clamp-2">
              {cardVO.description}
            </div>
          </div>

          <div className="w-full flex flex-row items-start justify-start gap-[0.6rem]">
            <div className="flex h-full flex-row items-center justify-center gap-[0.4rem]">
              <svg
                className="w-[1.2rem] h-[1.2rem] text-black"
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 24 24"
                fill="currentColor"
              >
                <path d="M24 12L18.3431 17.6569L16.9289 16.2426L21.1716 12L16.9289 7.75736L18.3431 6.34315L24 12ZM2.82843 12L7.07107 16.2426L5.65685 17.6569L0 12L5.65685 6.34315L7.07107 7.75736L2.82843 12ZM9.78845 21H7.66009L14.2116 3H16.3399L9.78845 21Z"></path>
              </svg>
              <div className="text-base text-black font-medium">
                {t('plugins.eventCount', {
                  count: Object.keys(cardVO.event_handlers).length,
                })}
              </div>
            </div>

            <div className="flex h-full flex-row items-center justify-center gap-[0.4rem]">
              <svg
                className="w-[1.2rem] h-[1.2rem] text-black"
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 24 24"
                fill="currentColor"
              >
                <path d="M5.32943 3.27158C6.56252 2.8332 7.9923 3.10749 8.97927 4.09446C10.1002 5.21537 10.3019 6.90741 9.5843 8.23385L20.293 18.9437L18.8788 20.3579L8.16982 9.64875C6.84325 10.3669 5.15069 10.1654 4.02952 9.04421C3.04227 8.05696 2.7681 6.62665 3.20701 5.39332L5.44373 7.63C6.02952 8.21578 6.97927 8.21578 7.56505 7.63C8.15084 7.04421 8.15084 6.09446 7.56505 5.50868L5.32943 3.27158ZM15.6968 5.15512L18.8788 3.38736L20.293 4.80157L18.5252 7.98355L16.7574 8.3371L14.6361 10.4584L13.2219 9.04421L15.3432 6.92289L15.6968 5.15512ZM8.97927 13.2868L10.3935 14.7011L5.09018 20.0044C4.69966 20.3949 4.06649 20.3949 3.67597 20.0044C3.31334 19.6417 3.28744 19.0699 3.59826 18.6774L3.67597 18.5902L8.97927 13.2868Z"></path>
              </svg>
              <div className="text-base text-black font-medium">
                {t('plugins.toolCount', { count: cardVO.tools.length })}
              </div>
            </div>
          </div>
        </div>

        <div className="flex flex-col items-center justify-between h-full">
          <div className="flex items-center justify-center">
            <Switch
              className="cursor-pointer"
              checked={enabled}
              onClick={(e) => handleEnable(e)}
              disabled={!switchEnable}
            />
          </div>

          {cardVO.repository &&
            cardVO.repository.trim() &&
            cardVO.repository.startsWith('http') && (
              <div className="flex items-center justify-center gap-[0.4rem]">
                <svg
                  className={`w-[1.4rem] h-[1.4rem] cursor-pointer ${
                    cardVO.repository ? 'text-black' : 'text-gray-400'
                  }`}
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="currentColor"
                  onClick={(e) => {
                    e.stopPropagation(); // 阻止事件冒泡
                    if (
                      cardVO.repository &&
                      cardVO.repository.trim() &&
                      cardVO.repository.startsWith('http')
                    ) {
                      window.open(cardVO.repository, '_blank');
                    }
                  }}
                >
                  <path d="M12.001 2C6.47598 2 2.00098 6.475 2.00098 12C2.00098 16.425 4.86348 20.1625 8.83848 21.4875C9.33848 21.575 9.52598 21.275 9.52598 21.0125C9.52598 20.775 9.51348 19.9875 9.51348 19.15C7.00098 19.6125 6.35098 18.5375 6.15098 17.975C6.03848 17.6875 5.55098 16.8 5.12598 16.5625C4.77598 16.375 4.27598 15.9125 5.11348 15.9C5.90098 15.8875 6.46348 16.625 6.65098 16.925C7.55098 18.4375 8.98848 18.0125 9.56348 17.75C9.65098 17.1 9.91348 16.6625 10.201 16.4125C7.97598 16.1625 5.65098 15.3 5.65098 11.475C5.65098 10.3875 6.03848 9.4875 6.67598 8.7875C6.57598 8.5375 6.22598 7.5125 6.77598 6.1375C6.77598 6.1375 7.61348 5.875 9.52598 7.1625C10.326 6.9375 11.176 6.825 12.026 6.825C12.876 6.825 13.726 6.9375 14.526 7.1625C16.4385 5.8625 17.276 6.1375 17.276 6.1375C17.826 7.5125 17.476 8.5375 17.376 8.7875C18.0135 9.4875 18.401 10.375 18.401 11.475C18.401 15.3125 16.0635 16.1625 13.8385 16.4125C14.201 16.725 14.5135 17.325 14.5135 18.2625C14.5135 19.6 14.501 20.675 14.501 21.0125C14.501 21.275 14.6885 21.5875 15.1885 21.4875C19.259 20.1133 21.9999 16.2963 22.001 12C22.001 6.475 17.526 2 12.001 2Z"></path>
                </svg>
              </div>
            )}
        </div>
      </div>
    </div>
  );
}
