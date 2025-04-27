import styles from "./pluginMarketCard.module.css"
import {GithubOutlined, StarOutlined} from '@ant-design/icons';
import {PluginMarketCardVO} from "@/app/home/plugins/plugin-market/plugin-market-card/PluginMarketCardVO";
import {Button} from "antd";

export default function PluginMarketCardComponent({
     cardVO
}: {
    cardVO: PluginMarketCardVO
}) {


    function handleInstallClick (pluginId: string) {
        console.log("Install plugin: ", pluginId)
    }

    return (
        <div className={`${styles.cardContainer}`}>
            {/*  header  */}
            <div className={`${styles.cardHeader}`}>
                {/* left author */}
                <div className={`${styles.fontGray}`}>{cardVO.author}</div>
                {/*  right icon */}
                <GithubOutlined
                    style={{fontSize: '26px'}}
                    type="setting"
                />
            </div>
            {/*  content  */}
            <div className={`${styles.cardContent}`}>
                <div className={`${styles.boldFont}`}>{cardVO.name}</div>
                <div className={`${styles.fontGray}`}>{cardVO.description}</div>
            </div>
            {/*  footer  */}
            <div className={`${styles.cardFooter}`}>
                <div className={`${styles.linkSettingContainer}`}>
                    <div className={`${styles.link}`}>
                        <StarOutlined
                            style={{fontSize: '22px'}}
                        />
                        <span>{cardVO.starCount}</span>
                    </div>
                </div>
                <Button
                    type="primary"
                    size={"small"}
                    onClick={() => {
                        handleInstallClick(cardVO.pluginId)
                    }}
                >
                    安装
                </Button>
            </div>
        </div>
    );
}
