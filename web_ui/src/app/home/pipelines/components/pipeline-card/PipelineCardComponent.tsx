import styles from "./pipelineCard.module.css";
import {PipelineCardVO} from "@/app/home/pipelines/components/pipeline-card/PipelineCardVO";

export default function PipelineCardComponent({
    cardVO
}: {
    cardVO: PipelineCardVO
}) {
    return (
        <div className={`${styles.cardContainer}`}>
            {/*  icon和基本信息  */}
            <div className={`${styles.iconBasicInfoContainer}`}>
                {/*  icon  */}
                <div className={`${styles.icon}`}>
                    ICO
                </div>
                {/*  基本信息  */}
                <div className={`${styles.basicInfoContainer}`}>
                    <div className={`${styles.basicInfoText}  ${styles.bigText}`}>
                        {cardVO.name}
                    </div>
                    <div className={`${styles.basicInfoText}`}>
                        描述：{cardVO.description}
                    </div>
                </div>
            </div>
            {/*  URL和创建时间  */}
            <div className={`${styles.urlAndUpdateText}`}>
                版本：{cardVO.version}
            </div>
        </div>
    );
}