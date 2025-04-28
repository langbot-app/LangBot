"use client"

import CreateCardComponent from "@/app/infra/basic-component/create-card-component/CreateCardComponent";
import { PluginCardVO } from "@/app/home/plugins/plugin-installed/PluginCardVO";
import { useEffect, useState } from "react";
import PluginCardComponent from "@/app/home/plugins/plugin-installed/plugin-card/PluginCardComponent";
import styles from "@/app/home/plugins/plugins.module.css";
import { Modal, Input } from "antd";
import { GithubOutlined } from "@ant-design/icons";

export default function PluginInstalledComponent() {
    const [pluginList, setPluginList] = useState<PluginCardVO[]>([])
    const [modalOpen, setModalOpen] = useState(false)
    const [githubURL, setGithubURL] = useState("")


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
            }), new PluginCardVO({
                description: "一般的描述",
                handlerCount: 0,
                name: "插件AAA",
                author: "/hana",
                version: "0.1"
            }), new PluginCardVO({
                description: "一般的描述",
                handlerCount: 0,
                name: "插件AAA",
                author: "/hana",
                version: "0.1"
            }), new PluginCardVO({
                description: "一般的描述",
                handlerCount: 0,
                name: "插件AAA",
                author: "/hana",
                version: "0.1"
            }), new PluginCardVO({
                description: "一般的描述",
                handlerCount: 0,
                name: "插件AAA",
                author: "/hana",
                version: "0.1"
            }), new PluginCardVO({
                description: "一般的描述",
                handlerCount: 0,
                name: "插件AAA",
                author: "/hana",
                version: "0.1"
            }), new PluginCardVO({
                description: "一般的描述",
                handlerCount: 0,
                name: "插件AAA",
                author: "/hana",
                version: "0.1"
            }), new PluginCardVO({
                description: "一般的描述",
                handlerCount: 0,
                name: "插件AAA",
                author: "/hana",
                version: "0.1"
            }), new PluginCardVO({
                description: "一般的描述",
                handlerCount: 0,
                name: "插件AAA",
                author: "/hana",
                version: "0.1"
            }), new PluginCardVO({
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
            }), new PluginCardVO({
                description: "一般的描述",
                handlerCount: 0,
                name: "插件AAA",
                author: "/hana",
                version: "0.1"
            }), new PluginCardVO({
                description: "一般的描述",
                handlerCount: 0,
                name: "插件AAA",
                author: "/hana",
                version: "0.1"
            }), new PluginCardVO({
                description: "一般的描述",
                handlerCount: 0,
                name: "插件AAA",
                author: "/hana",
                version: "0.1"
            }), new PluginCardVO({
                description: "一般的描述",
                handlerCount: 0,
                name: "插件AAA",
                author: "/hana",
                version: "0.1"
            }), new PluginCardVO({
                description: "一般的描述",
                handlerCount: 0,
                name: "插件AAA",
                author: "/hana",
                version: "0.1"
            }), new PluginCardVO({
                description: "一般的描述",
                handlerCount: 0,
                name: "插件AAA",
                author: "/hana",
                version: "0.1"
            }), new PluginCardVO({
                description: "一般的描述",
                handlerCount: 0,
                name: "插件AAA",
                author: "/hana",
                version: "0.1"
            }), new PluginCardVO({
                description: "一般的描述",
                handlerCount: 0,
                name: "插件AAA",
                author: "/hana",
                version: "0.1"
            }), new PluginCardVO({
                description: "一般的描述",
                handlerCount: 0,
                name: "插件AAA",
                author: "/hana",
                version: "0.1"
            }), new PluginCardVO({
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

    function handleModalConfirm() {
        installPlugin(githubURL)
        setModalOpen(false)
    }

    function installPlugin(url: string) {
        // TODO 接安装Plugin的接口
        console.log("installPlugin: ", url)
    }
    return (
        <div className={`${styles.pluginListContainer}`}>
            <Modal
                title={
                    <div className={`${styles.modalTitle}`}>
                        <GithubOutlined
                            style={{
                                fontSize: '30px',
                                marginRight: '20px'
                            }}
                            type="setting"
                        />
                        <span>从 GitHub 安装插件</span>
                    </div>
                }
                centered
                open={modalOpen}
                onOk={() => handleModalConfirm()}
                onCancel={() => setModalOpen(false)}
                width={500}
                destroyOnClose={true}
            >
                <div className={`${styles.modalBody}`}>
                    <div>
                        目前仅支持从 GitHub 安装
                    </div>
                    <Input
                        placeholder="请输入插件的Github链接"
                        value={githubURL}
                        onChange={(e) => setGithubURL(e.target.value)}
                    />
                </div>
            </Modal>
            {
                pluginList.map((vo, index) => {
                    return <div key={index}>
                        <PluginCardComponent cardVO={vo} />
                    </div>
                })
            }
            <CreateCardComponent
                height={140}
                plusSize={90}
                onClick={() => {
                    setModalOpen(true)
                }}
            />
        </div>
    )
}
