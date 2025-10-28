import { MCPMarketCardVO } from '@/app/home/plugins/mcp-server/mcp-server-card/MCPServerCardVO';
import { Button } from '@/components/ui/button';
import { useTranslation } from 'react-i18next';

export default function MCPMarketCardComponent({
  cardVO,
  installServer,
}: {
  cardVO: MCPMarketCardVO;
  installServer: (serverURL: string) => void;
}) {
  const { t } = useTranslation();

  function handleInstallClick(serverURL: string) {
    installServer(serverURL);
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
          <path d="M13.5 2C13.5 2.82843 14.1716 3.5 15 3.5C15.8284 3.5 16.5 2.82843 16.5 2C16.5 1.17157 15.8284 0.5 15 0.5C14.1716 0.5 13.5 1.17157 13.5 2ZM8.5 8C8.5 8.82843 9.17157 9.5 10 9.5C10.8284 9.5 11.5 8.82843 11.5 8C11.5 7.17157 10.8284 6.5 10 6.5C9.17157 6.5 8.5 7.17157 8.5 8ZM1.5 14C1.5 14.8284 2.17157 15.5 3 15.5C3.82843 15.5 4.5 14.8284 4.5 14C4.5 13.1716 3.82843 12.5 3 12.5C2.17157 12.5 1.5 13.1716 1.5 14ZM19.5 14C19.5 14.8284 20.1716 15.5 21 15.5C21.8284 15.5 22.5 14.8284 22.5 14C22.5 13.1716 21.8284 12.5 21 12.5C20.1716 12.5 19.5 13.1716 19.5 14ZM8.5 20C8.5 20.8284 9.17157 21.5 10 21.5C10.8284 21.5 11.5 20.8284 11.5 20C11.5 19.1716 10.8284 19 10 19C9.17157 19 8.5 19.1716 8.5 20ZM2.5 8L6.5 8L6.5 10L2.5 10L2.5 8ZM13.5 8L17.5 8L17.5 10L13.5 10L13.5 8ZM8.5 2L8.5 6L10.5 6L10.5 2L8.5 2ZM8.5 14L8.5 18L10.5 18L10.5 14L8.5 14ZM2.5 14L6.5 14L6.5 16L2.5 16L2.5 14ZM13.5 14L17.5 14L17.5 16L13.5 16L13.5 14Z"></path>
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
                {t('mcp.starCount', { count: cardVO.starCount })}
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
                {t('mcp.install')}
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
