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

          <div className="flex items-center justify-center">
            {/* <Button variant="ghost">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M6.17071 18C6.58254 16.8348 7.69378 16 9 16C10.3062 16 11.4175 16.8348 11.8293 18H22V20H11.8293C11.4175 21.1652 10.3062 22 9 22C7.69378 22 6.58254 21.1652 6.17071 20H2V18H6.17071ZM12.1707 11C12.5825 9.83481 13.6938 9 15 9C16.3062 9 17.4175 9.83481 17.8293 11H22V13H17.8293C17.4175 14.1652 16.3062 15 15 15C13.6938 15 12.5825 14.1652 12.1707 13H2V11H12.1707ZM6.17071 4C6.58254 2.83481 7.69378 2 9 2C10.3062 2 11.4175 2.83481 11.8293 4H22V6H11.8293C11.4175 7.16519 10.3062 8 9 8C7.69378 8 6.58254 7.16519 6.17071 6H2V4H6.17071ZM9 6C9.55228 6 10 5.55228 10 5C10 4.44772 9.55228 4 9 4C8.44772 4 8 4.44772 8 5C8 5.55228 8.44772 6 9 6ZM15 13C15.5523 13 16 12.5523 16 12C16 11.4477 15.5523 11 15 11C14.4477 11 14 11.4477 14 12C14 12.5523 14.4477 13 15 13ZM9 20C9.55228 20 10 19.5523 10 19C10 18.4477 9.55228 18 9 18C8.44772 18 8 18.4477 8 19C8 19.5523 8.44772 20 9 20Z"></path></svg>
            </Button> */}
          </div>
        </div>
      </div>
    </div>
  );
}
