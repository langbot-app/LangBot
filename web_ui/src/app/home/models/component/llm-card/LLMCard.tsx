import styles from "../../LLMConfig.module.css"
import {LLMCardVO} from "@/app/home/models/component/llm-card/LLMCardVO";

export default function LLMCard({
    cardVO
}: {
    cardVO: LLMCardVO
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
                        {cardVO.name}
                    </div>
                    <div className={`${styles.basicInfoText}`}>
                        使用模型：{cardVO.model}
                    </div>
                    <div className={`${styles.basicInfoText}`}>
                        厂商：{cardVO.company}
                    </div>
                </div>
            </div>
            {/*  URL和创建时间  */}
            <div className={`${styles.urlAndUpdateText}`}>
                URL：{cardVO.URL}
            </div>
        </div>
    );
}