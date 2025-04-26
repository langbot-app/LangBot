import styles from "./pluginCard.module.css"
import {PluginCardVO} from "@/app/home/plugins/plugin-installed/PluginCardVO";

export default function PluginCardComponent({
    cardVO
}: {
    cardVO: PluginCardVO
}) {
    return (
        <div className={`${styles.cardContainer}`}>
            {/*  header  */}
            <div className={`${styles.cardHeader}`}>
                {/* left author */}
                <div className={`${styles.fontGray}`}>{cardVO.author}</div>
                {/*  right icon & version  */}
                <div className={`${styles.iconVersionContainer}`}>

                </div>
            </div>
            {/*  content  */}
            <div className={`${styles.cardContent}`}>
                <div className={`${styles.boldFont}`}>{cardVO.name}</div>
                <div className={`${styles.fontGray}`}>{cardVO.description}</div>
            </div>
            {/*  footer  */}
            <div className={`${styles.cardFooter}`}>
                <div className={`${styles.iconVersionContainer}`}>

                </div>
            </div>
        </div>
    );
}
