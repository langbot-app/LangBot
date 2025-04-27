"use client"

import {useCallback, useEffect, useState} from "react";
import styles from "@/app/home/plugins/plugins.module.css";
import {PluginMarketCardVO} from "@/app/home/plugins/plugin-market/plugin-market-card/PluginMarketCardVO";
import PluginMarketCardComponent from "@/app/home/plugins/plugin-market/plugin-market-card/PluginMarketCardComponent";
import {Input} from "antd";
import {debounce} from "lodash"

export default function PluginInstalledComponent () {
    const [marketPluginList, setMarketPluginList] = useState<PluginMarketCardVO[]>([])
    const [searchKeyword, setSearchKeyword] = useState("")

    useEffect(() => {
        initData()
    }, [])

    function initData() {
        getPluginList().then((value) => {
            setMarketPluginList(value)
        })
    }

    function onInputSearchKeyword(keyword: string) {
        setSearchKeyword(keyword)
        debounceSearch(keyword)
    }

    const debounceSearch = useCallback(
        debounce((keyword: string) => {
            console.log("debounce search", keyword)
            searchPlugin(keyword).then(marketPluginList => {
                setMarketPluginList(marketPluginList)
            })
        }, 500), []
    )

    async function searchPlugin(keyword: string): Promise<PluginMarketCardVO[]> {
        // TODO 实现搜索
        const demoResult: PluginMarketCardVO[] =  []
        for (let i = 0; i < keyword.length; i ++) {
            demoResult.push(new PluginMarketCardVO({
                author: "/hanahana",
                description: "一个搜索测试的描述",
                githubURL: "？",
                name: "搜索插件" + i,
                pluginId: `${i}`,
                starCount: 19 + i,
                version: `0.${i}`,
            }))
        }
        return demoResult
    }

    async function getPluginList(): Promise<PluginMarketCardVO[]> {
        return [
            new PluginMarketCardVO({
                pluginId: "aaa",
                description: "一般的描述",
                name: "插件AAA",
                author: "/hana",
                version: "0.1",
                githubURL: "",
                starCount: 23
            }),
        ]
    }

    return (
        <div className={`${styles.pluginListContainer}`}>
            <Input
                value={searchKeyword}
                onChange={(e) => onInputSearchKeyword(e.target.value)}
            />
            {
                marketPluginList.map((vo, index) => {
                    return <div key={index}>
                        <PluginMarketCardComponent cardVO={vo}/>
                    </div>
                })
            }
        </div>
    )
}
