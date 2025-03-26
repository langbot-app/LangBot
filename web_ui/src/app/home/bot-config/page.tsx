"use client"

import {useEffect, useState} from "react";
import styles from "./botConfig.module.css";
import EmptyAndCreateComponent from "@/app/home/components/empty-and-create-component/EmptyAndCreateComponent";
import {useRouter} from "next/navigation";
import {BotCardVO} from "@/app/home/bot-config/components/bot-card/BotCardVO";
import {Modal} from "antd";
import BotForm from "@/app/home/bot-config/components/bot-form/BotForm";
import BotCard from "@/app/home/bot-config/components/bot-card/BotCard";
import CreateCardComponent from "@/app/infra/basic-component/create-card-component/CreateCardComponent"


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
                const botList = getBotList()
                if (botList.length === 0) {
                    setPageShowRule(BotConfigPageShowRule.NO_BOT)
                } else {
                    setPageShowRule(BotConfigPageShowRule.HAVE_BOT)
                }
                setBotList(botList)
            } else {
                setPageShowRule(BotConfigPageShowRule.NO_LLM)
            }
        })
    }, [])

    async function checkHasLLM(): Promise<boolean> {
        // NOT IMPL
        return true
    }

    function getBotList(): BotCardVO[] {
        let botList: BotCardVO[] = [
            new BotCardVO({
                adapter: "QQ bot",
                description: "1111",
                id: "1111",
                name: "第一个bot",
                updateTime: "202300001111",
                pipelineName: "默认流水线",
            }),
            new BotCardVO({
                adapter: "WX bot",
                description: "22211",
                id: "2222",
                name: "第2个bot",
                updateTime: "2025011011",
                pipelineName: "默认流水线",
            }),
        ]
        // botList = []
        return botList
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
                        router.push("/home/llm-config");
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