import {BotCardVO} from "@/app/home/bots/components/bot-card/BotCardVO";
import styles from "./botCard.module.css";

export default function BotCard({
    botCardVO
}: {
    botCardVO: BotCardVO;
}) {
    return (
        <div className={`${styles.cardContainer}`}>
            {/*  icon和基本信息  */}
            <div className={`${styles.iconBasicInfoContainer}`}>
                {/*  icon  */}
                <div className={`${styles.icon}`}>
                    ICO
                </div>
                {/*  bot基本信息  */}
                <div className={`${styles.basicInfoContainer}`}>
                    <div className={`${styles.basicInfoText}  ${styles.bigText}`}>
                        {botCardVO.name}
                    </div>
                    <div className={`${styles.basicInfoText}`}>
                        平台：{botCardVO.adapter}
                    </div>
                    <div className={`${styles.basicInfoText}`}>
                        绑定流水线：{botCardVO.pipelineName}
                    </div>
                </div>
            </div>
            {/*  描述和创建时间  */}
            <div className={`${styles.urlAndUpdateText}`}>
                描述：{botCardVO.description}
            </div>
            <div className={`${styles.urlAndUpdateText}`}>
                更新时间：{botCardVO.updateTime}
            </div>
        </div>
    )
}