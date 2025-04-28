import styles from "./pluginCard.module.css"
import { PluginCardVO } from "@/app/home/plugins/plugin-installed/PluginCardVO";
import { GithubOutlined, LinkOutlined, ToolOutlined } from '@ant-design/icons';
import { Tag } from 'antd'

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
                    <GithubOutlined
                        style={{ fontSize: '26px' }}
                        type="setting"
                    />
                    <Tag color="#108ee9">v{cardVO.version}</Tag>
                </div>
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
                        <LinkOutlined
                            style={{ fontSize: '22px' }}
                        />
                        <span>1</span>
                    </div>
                    <ToolOutlined
                        style={{ fontSize: '22px' }}
                    />
                </div>
            </div>
        </div>
    );
}
