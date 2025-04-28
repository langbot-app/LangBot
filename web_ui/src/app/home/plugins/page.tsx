"use client"
import { Radio } from 'antd';
import { useState } from "react";
import PluginInstalledComponent from "@/app/home/plugins/plugin-installed/PluginInstalledComponent";
import PluginMarketComponent from "@/app/home/plugins/plugin-market/PluginMarketComponent";
import styles from './plugins.module.css'

export default function PluginConfigPage() {
    enum PageType {
        INSTALLED = "installed",
        MARKET = 'market'
    }

    const [nowPageType, setNowPageType] = useState(PageType.INSTALLED)

    return (
        <div className={`${styles.pageContainer}`}>
            <div className="up"  style={{ marginBottom: '20px' }}>
                <Radio.Group
                    block
                    options={[
                        { label: '已安装', value: PageType.INSTALLED },
                        { label: '插件市场', value: PageType.MARKET },
                    ]}
                    defaultValue={PageType.INSTALLED}
                    value={nowPageType}
                    optionType="button"
                    buttonStyle="solid"
                    onChange={(e) => {
                        // 这里静态类型检测有问题
                        setNowPageType(e.target.value)
                    }}
                /></div>
            <div className="down">
                <div className={`${styles.pageContainer}`}>
                    {
                        nowPageType === PageType.INSTALLED && <PluginInstalledComponent />
                    }
                    {
                        nowPageType === PageType.MARKET && <PluginMarketComponent />
                    }
                </div></div>


        </div>
    );
}
