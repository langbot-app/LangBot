import { BotCardVO } from '@/app/home/bots/components/bot-card/BotCardVO';
import styles from './botCard.module.css';

export default function BotCard({ botCardVO }: { botCardVO: BotCardVO }) {
  return (
    <div className={`${styles.cardContainer}`}>
      <div className={`${styles.iconBasicInfoContainer}`}>
        <img
          className={`${styles.iconImage}`}
          src={botCardVO.iconURL}
          alt="icon"
        />

        <div className={`${styles.basicInfoContainer}`}>
          <div className={`${styles.basicInfoNameContainer}`}>
            <div className={`${styles.basicInfoName}`}>{botCardVO.name}</div>
            <div className={`${styles.basicInfoDescription}`}>
              {botCardVO.description}
            </div>
          </div>

          <div className={`${styles.basicInfoAdapterContainer}`}>
            <svg
              className={`${styles.basicInfoAdapterIcon}`}
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="currentColor"
            >
              <path d="M2 8.99374C2 5.68349 4.67654 3 8.00066 3H15.9993C19.3134 3 22 5.69478 22 8.99374V21H8.00066C4.68659 21 2 18.3052 2 15.0063V8.99374ZM20 19V8.99374C20 6.79539 18.2049 5 15.9993 5H8.00066C5.78458 5 4 6.78458 4 8.99374V15.0063C4 17.2046 5.79512 19 8.00066 19H20ZM14 11H16V13H14V11ZM8 11H10V13H8V11Z"></path>
            </svg>
            <span className={`${styles.basicInfoAdapterLabel}`}>
              {botCardVO.adapterLabel}
            </span>
          </div>

          <div className={`${styles.basicInfoPipelineContainer}`}>
            <svg
              className={`${styles.basicInfoPipelineIcon}`}
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="currentColor"
            >
              <path d="M6 21.5C4.067 21.5 2.5 19.933 2.5 18C2.5 16.067 4.067 14.5 6 14.5C7.5852 14.5 8.92427 15.5539 9.35481 16.9992L15 16.9994V15L17 14.9994V9.24339L14.757 6.99938H9V9.00003H3V3.00003H9V4.99939H14.757L18 1.75739L22.2426 6.00003L19 9.24139V14.9994L21 15V21H15V18.9994L9.35499 19.0003C8.92464 20.4459 7.58543 21.5 6 21.5ZM6 16.5C5.17157 16.5 4.5 17.1716 4.5 18C4.5 18.8285 5.17157 19.5 6 19.5C6.82843 19.5 7.5 18.8285 7.5 18C7.5 17.1716 6.82843 16.5 6 16.5ZM19 17H17V19H19V17ZM18 4.58581L16.5858 6.00003L18 7.41424L19.4142 6.00003L18 4.58581ZM7 5.00003H5V7.00003H7V5.00003Z"></path>
            </svg>
            <span className={`${styles.basicInfoPipelineLabel}`}>
              {botCardVO.usePipelineName}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
