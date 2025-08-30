import { PluginMarketCardVO } from './PluginMarketCardVO';

export default function PluginMarketCardComponent({
  cardVO,
  onPluginClick,
}: {
  cardVO: PluginMarketCardVO;
  onPluginClick?: (author: string, pluginName: string) => void;
}) {
  function handleCardClick() {
    if (onPluginClick) {
      onPluginClick(cardVO.author, cardVO.pluginName);
    }
  }

  return (
    <div
      className="w-[100%] h-[9rem] bg-white rounded-[10px] shadow-[0px_0px_4px_0_rgba(0,0,0,0.2)] p-[1rem] cursor-pointer hover:shadow-[0px_2px_8px_0_rgba(0,0,0,0.15)] transition-shadow duration-200 dark:bg-[#1f1f22]"
      onClick={handleCardClick}
    >
      <div className="w-full h-full flex flex-col justify-between">
        {/* 上部分：插件信息 */}
        <div className="flex flex-row items-start justify-start gap-[1.2rem]">
          <img src={cardVO.iconURL} alt="plugin icon" className="w-16 h-16" />

          <div className="flex-1 flex flex-col items-start justify-start gap-[0.6rem]">
            <div className="flex flex-col items-start justify-start">
              <div className="text-[0.7rem] text-[#666] dark:text-[#999]">
                {cardVO.pluginId}
              </div>
              <div className="flex flex-row items-center justify-start gap-[0.4rem]">
                <div className="text-[1.2rem] text-black dark:text-[#f0f0f0]">
                  {cardVO.label}
                </div>
              </div>
            </div>

            <div className="text-[0.8rem] text-[#666] dark:text-[#999] line-clamp-2">
              {cardVO.description}
            </div>
          </div>

          <div className="flex h-full flex-row items-start justify-center gap-[0.4rem]">
            {cardVO.githubURL && (
              <svg
                className="w-[1.4rem] h-[1.4rem] text-black cursor-pointer hover:text-gray-600 dark:text-[#f0f0f0]"
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 24 24"
                fill="currentColor"
                onClick={(e) => {
                  e.stopPropagation();
                  window.open(cardVO.githubURL, '_blank');
                }}
              >
                <path d="M12.001 2C6.47598 2 2.00098 6.475 2.00098 12C2.00098 16.425 4.86348 20.1625 8.83848 21.4875C9.33848 21.575 9.52598 21.275 9.52598 21.0125C9.52598 20.775 9.51348 19.9875 9.51348 19.15C7.00098 19.6125 6.35098 18.5375 6.15098 17.975C6.03848 17.6875 5.55098 16.8 5.12598 16.5625C4.77598 16.375 4.27598 15.9125 5.11348 15.9C5.90098 15.8875 6.46348 16.625 6.65098 16.925C7.55098 18.4375 8.98848 18.0125 9.56348 17.75C9.65098 17.1 9.91348 16.6625 10.201 16.4125C7.97598 16.1625 5.65098 15.3 5.65098 11.475C5.65098 10.3875 6.03848 9.4875 6.67598 8.7875C6.57598 8.5375 6.22598 7.5125 6.77598 6.1375C6.77598 6.1375 7.61348 5.875 9.52598 7.1625C10.326 6.9375 11.176 6.825 12.026 6.825C12.876 6.825 13.726 6.9375 14.526 7.1625C16.4385 5.8625 17.276 6.1375 17.276 6.1375C17.826 7.5125 17.476 8.5375 17.376 8.7875C18.0135 9.4875 18.401 10.375 18.401 11.475C18.401 15.3125 16.0635 16.1625 13.8385 16.4125C14.201 16.725 14.5135 17.325 14.5135 18.2625C14.5135 19.6 14.501 20.675 14.501 21.0125C14.501 21.275 14.6885 21.5875 15.1885 21.4875C19.259 20.1133 21.9999 16.2963 22.001 12C22.001 6.475 17.526 2 12.001 2Z"></path>
              </svg>
            )}
          </div>
        </div>

        {/* 下部分：下载量 */}
        <div className="w-full flex flex-row items-center justify-start gap-[0.4rem] px-[0.4rem]">
          <svg
            className="w-[1.2rem] h-[1.2rem] text-[#2563eb]"
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="7,10 12,15 17,10" />
            <line x1="12" y1="15" x2="12" y2="3" />
          </svg>
          <div className="text-sm text-[#2563eb] font-medium">
            {cardVO.installCount.toLocaleString()}
          </div>
        </div>
      </div>
    </div>
  );
}
