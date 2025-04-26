"use client"

import {useEffect, useState} from "react";
import styles from "./botConfig.module.css";
import EmptyAndCreateComponent from "@/app/home/components/empty-and-create-component/EmptyAndCreateComponent";
import {useRouter} from "next/navigation";
import {BotCardVO} from "@/app/home/bots/components/bot-card/BotCardVO";
import {Modal} from "antd";
import BotForm from "@/app/home/bots/components/bot-form/BotForm";
import BotCard from "@/app/home/bots/components/bot-card/BotCard";
import CreateCardComponent from "@/app/infra/basic-component/create-card-component/CreateCardComponent"
import {httpClient} from "@/app/infra/http/HttpClient";


export default function BotConfigPage() {
    const router = useRouter();
    const [pageShowRule, setPageShowRule] = useState<BotConfigPageShowRule>(BotConfigPageShowRule.NO_BOT)
    const [modalOpen, setModalOpen] = useState<boolean>(false);
    const [botList, setBotList] = useState<BotCardVO[]>([])
    const [isEditForm, setIsEditForm] = useState(false)
    const [nowSelectedBotCard, setNowSelectedBotCard] = useState<BotCardVO>()

    useEffect(() => {
        // TODO：补齐加载转圈逻辑
        checkHasLLM().then((hasLLM) => {
            if (hasLLM) {
                getBotList().then((botList) => {
                    if (botList.length === 0) {
                        setPageShowRule(BotConfigPageShowRule.NO_BOT)
                    } else {
                    setPageShowRule(BotConfigPageShowRule.HAVE_BOT)
                    }
                    setBotList(botList)
                }).catch((err) => {
                    // TODO error toast
                    console.error("get bot list error (useEffect)", err)
                })
            } else {
                setPageShowRule(BotConfigPageShowRule.NO_LLM)
            }
        })
    }, [])

    async function checkHasLLM(): Promise<boolean> {
        // NOT IMPL
        return true
    }

    function getBotList(): Promise<BotCardVO[]> {

        return new Promise((resolve) => {
            httpClient.getBots().then((resp) => {
                console.log("get bot list (getBotList)", resp)
                const botList: BotCardVO[] = resp.bots.map((bot: any) => {
                    return new BotCardVO({
                        adapter: bot.adapter,
                        description: bot.description,
                        id: bot.id,
                        name: bot.name,
                        updateTime: bot.update_time,
                        pipelineName: bot.pipeline_name,
                    })
                })
                resolve(botList)
            }).catch((err) => {
                // TODO error toast
                console.error("get bot list error", err)
                resolve([])
            })
        })
    }

    function handleCreateBotClick() {
        setIsEditForm(false)
        setNowSelectedCard(undefined)
        setModalOpen(true);
    }

    function setNowSelectedCard(cardVO: BotCardVO | undefined) {
        setNowSelectedBotCard(cardVO)
    }

    function selectBot(cardVO: BotCardVO) {
        setIsEditForm(true)
        setNowSelectedCard(cardVO)
        console.log("set now vo", cardVO)
        setModalOpen(true)
    }

    return (
        <div className={styles.configPageContainer}>
            <Modal
                title={isEditForm ? "编辑机器人" : "创建机器人"}
                centered
                open={modalOpen}
                onOk={() => setModalOpen(false)}
                onCancel={() => setModalOpen(false)}
                width={700}
                footer={null}
                destroyOnClose={true}
            >
                <BotForm
                    initBotId={nowSelectedBotCard?.id}
                    onFormSubmit={() => setIsEditForm(false)}
                    onFormCancel={() => setModalOpen(false)}
                />
            </Modal>
            {pageShowRule === BotConfigPageShowRule.NO_LLM &&
                <EmptyAndCreateComponent
                    title={"需要先创建大模型才能配置机器人哦～"}
                    subTitle={"快去创建一个吧！"}
                    buttonText={"创建大模型 GO！"}
                    onButtonClick={() => {
                        router.push("/home/models");
                    }}
                />
            }

            {pageShowRule === BotConfigPageShowRule.NO_BOT &&
                 <EmptyAndCreateComponent
                     title={"您还未配置机器人哦～"}
                     subTitle={"快去创建一个吧！"}
                     buttonText={"创建机器人 +"}
                     onButtonClick={handleCreateBotClick}
                 />
            }

            {pageShowRule === BotConfigPageShowRule.HAVE_BOT &&
             <div className={`${styles.botListContainer}`}
             >
                 {botList.map(cardVO => {
                     return (
                     <div
                         key={cardVO.id}
                         onClick={() => {selectBot(cardVO)}}
                     >
                        <BotCard botCardVO={cardVO} />
                     </div>)
                 })}
                 <CreateCardComponent
                     width={360}
                     height={200}
                     plusSize={90}
                     onClick={handleCreateBotClick}
                 />
             </div>
            }
        </div>
    )
}

enum BotConfigPageShowRule {
    NO_LLM,
    NO_BOT,
    HAVE_BOT,
}