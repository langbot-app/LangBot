"use client"

import CreateCardComponent from "@/app/infra/basic-component/create-card-component/CreateCardComponent";
import {PluginCardVO} from "@/app/home/plugins/plugin-installed/PluginCardVO";
import {useEffect, useState} from "react";
import PluginCardComponent from "@/app/home/plugins/plugin-installed/plugin-card/PluginCardComponent";

export default function PluginInstalledComponent () {
    const [pluginList, setPluginList] = useState<PluginCardVO[]>([])

    useEffect(() => {
        initData()
    }, [])

    function initData() {
        getPluginList().then((value) => {
            setPluginList(value)
        })
    }

    async function getPluginList() {
        return [
            new PluginCardVO({
                description: "一般的描述",
                handlerCount: 0,
                name: "插件AAA",
                author: "/hana",
                version: "0.1"
            }),
            new PluginCardVO({
                description: "一般的描述",
                handlerCount: 0,
                name: "插件AAA",
                author: "/hana",
                version: "0.1"
            }),
            new PluginCardVO({
                description: "一般的描述",
                handlerCount: 0,
                name: "插件AAA",
                author: "/hana",
                version: "0.1"
            }),
            new PluginCardVO({
                description: "一般的描述",
                handlerCount: 0,
                name: "插件AAA",
                author: "/hana",
                version: "0.1"
            })
        ]
    }

    return (
        <div>
            {
                pluginList.map((vo, index) => {
                    return <div key={index}>
                        <PluginCardComponent cardVO={vo}/>
                    </div>
                })
            }
            <CreateCardComponent
                width={360}
                height={120}
                plusSize={90}
                onClick={() => {}}
            />
        </div>
    )
}
