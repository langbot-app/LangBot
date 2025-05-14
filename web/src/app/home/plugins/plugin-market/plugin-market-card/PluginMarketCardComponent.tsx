import { PluginMarketCardVO } from '@/app/home/plugins/plugin-market/plugin-market-card/PluginMarketCardVO';
import { Button } from '@/components/ui/button';
import { useTranslation } from 'react-i18next';

export default function PluginMarketCardComponent({
  cardVO,
  installPlugin,
}: {
  cardVO: PluginMarketCardVO;
  installPlugin: (pluginURL: string) => void;
}) {
  const { t } = useTranslation();

  function handleInstallClick(pluginURL: string) {
    installPlugin(pluginURL);
  }

  return (
    <div className="w-[100%] h-[10rem] bg-white rounded-[10px] shadow-[0px_2px_2px_0_rgba(0,0,0,0.2)] p-[1.2rem]">
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
              </div>
            </div>

            <div className="text-[0.8rem] text-[#666] line-clamp-2">
              {cardVO.description}
            </div>
          </div>

          <div className="w-full flex flex-row items-start justify-between gap-[0.6rem]">
            <div className="flex h-full flex-row items-center justify-center gap-[0.4rem]">
              <svg
                className="w-[1.2rem] h-[1.2rem] text-[#ffcd27]"
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 24 24"
                fill="currentColor"
              >
                <path d="M12.0006 18.26L4.94715 22.2082L6.52248 14.2799L0.587891 8.7918L8.61493 7.84006L12.0006 0.5L15.3862 7.84006L23.4132 8.7918L17.4787 14.2799L19.054 22.2082L12.0006 18.26Z"></path>
              </svg>
              <div className="text-base text-[#ffcd27] font-medium">
                {t('plugins.starCount', { count: cardVO.starCount })}
              </div>
            </div>

            <div className="flex h-full flex-row items-center justify-center gap-[0.4rem]">
              <svg
                className="w-[1.4rem] h-[1.4rem] text-black cursor-pointer"
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 24 24"
                fill="currentColor"
                onClick={() => window.open(cardVO.githubURL, '_blank')}
              >
                <path d="M12.001 2C6.47598 2 2.00098 6.475 2.00098 12C2.00098 16.425 4.86348 20.1625 8.83848 21.4875C9.33848 21.575 9.52598 21.275 9.52598 21.0125C9.52598 20.775 9.51348 19.9875 9.51348 19.15C7.00098 19.6125 6.35098 18.5375 6.15098 17.975C6.03848 17.6875 5.55098 16.8 5.12598 16.5625C4.77598 16.375 4.27598 15.9125 5.11348 15.9C5.90098 15.8875 6.46348 16.625 6.65098 16.925C7.55098 18.4375 8.98848 18.0125 9.56348 17.75C9.65098 17.1 9.91348 16.6625 10.201 16.4125C7.97598 16.1625 5.65098 15.3 5.65098 11.475C5.65098 10.3875 6.03848 9.4875 6.67598 8.7875C6.57598 8.5375 6.22598 7.5125 6.77598 6.1375C6.77598 6.1375 7.61348 5.875 9.52598 7.1625C10.326 6.9375 11.176 6.825 12.026 6.825C12.876 6.825 13.726 6.9375 14.526 7.1625C16.4385 5.8625 17.276 6.1375 17.276 6.1375C17.826 7.5125 17.476 8.5375 17.376 8.7875C18.0135 9.4875 18.401 10.375 18.401 11.475C18.401 15.3125 16.0635 16.1625 13.8385 16.4125C14.201 16.725 14.5135 17.325 14.5135 18.2625C14.5135 19.6 14.501 20.675 14.501 21.0125C14.501 21.275 14.6885 21.5875 15.1885 21.4875C19.259 20.1133 21.9999 16.2963 22.001 12C22.001 6.475 17.526 2 12.001 2Z"></path>
              </svg>
              <Button
                variant="default"
                size="sm"
                onClick={() => {
                  handleInstallClick(cardVO.githubURL);
                }}
                className="cursor-pointer"
              >
                {t('plugins.install')}
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
