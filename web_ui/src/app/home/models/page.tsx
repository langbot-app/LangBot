"use client"

import {useState} from "react";
import {LLMCardVO} from "@/app/home/models/component/llm-card/LLMCardVO";
import styles from "./LLMConfig.module.css"
import EmptyAndCreateComponent from "@/app/home/components/empty-and-create-component/EmptyAndCreateComponent";
import {Modal} from "antd";
import LLMCard from "@/app/home/models/component/llm-card/LLMCard";
import LLMForm from "@/app/home/models/component/llm-form/LLMForm";
import CreateCardComponent from "@/app/infra/basic-component/create-card-component/CreateCardComponent";

export default function LLMConfigPage() {
    const [cardList, setCardList] = useState<LLMCardVO[]>([
        new LLMCardVO({
            id: "1",
            name: "测试模型",
            model: "GPT-4o",
            URL: "www.openai.com",
            company: "OpenAI",
            updateTime: "2025.1.2"
        }),
        new LLMCardVO({
            id: "2",
            name: "测试模型",
            model: "GPT-4o",
            URL: "www.openai.com",
            company: "OpenAI",
            updateTime: "2025.1.2"
        }),
        new LLMCardVO({
            id: "3",
            name: "测试模型",
            model: "GPT-4o",
            URL: "www.openai.com",
            company: "OpenAI",
            updateTime: "2025.1.2"
        }),
        new LLMCardVO({
            id: "4",
            name: "测试模型",
            model: "GPT-4o",
            URL: "www.openai.com",
            company: "OpenAI",
            updateTime: "2025.1.2"
        }),
        new LLMCardVO({
            id: "5",
            name: "测试模型",
            model: "GPT-4o",
            URL: "www.openai.com",
            company: "OpenAI",
            updateTime: "2025.1.2"
        }),
    ])
    const [modalOpen, setModalOpen] = useState<boolean>(false);
    const [isEditForm, setIsEditForm] = useState(false)
    const [nowSelectedLLM, setNowSelectedLLM] = useState<LLMCardVO | null>(null)

    function selectLLM(cardVO: LLMCardVO) {
        setIsEditForm(true)
        setNowSelectedLLM(cardVO)
        console.log("set now vo", cardVO)
        setModalOpen(true)
    }
    function handleCreateModelClick() {
        setIsEditForm(false)
        setNowSelectedLLM(null)
        setModalOpen(true);
    }

    return (
        <div className={styles.configPageContainer}>
            <Modal
                title={isEditForm ? "编辑模型" : "创建模型"}
                centered
                open={modalOpen}
                onOk={() => setModalOpen(false)}
                onCancel={() => setModalOpen(false)}
                width={700}
                footer={null}
            >
                <LLMForm
                    editMode={isEditForm}
                    initLLMId={nowSelectedLLM?.id}
                    onFormSubmit={() => {
                        setModalOpen(false);
                    }}
                    onFormCancel={() => {
                        setModalOpen(false);
                    }}
                />
            </Modal>
            {
                cardList.length > 0 &&
                <div className={`${styles.modelListContainer}`}
                >
                    {cardList.map(cardVO => {
                        return <div key={cardVO.id} onClick={() => {selectLLM(cardVO)}}>
                            <LLMCard cardVO={cardVO}></LLMCard>
                        </div>
                    })}
                    <CreateCardComponent
                        width={360}
                        height={200}
                        plusSize={90}
                        onClick={handleCreateModelClick}
                    />
                </div>
            }

            {
                cardList.length === 0 &&
                <div className={`${styles.emptyContainer}`}>
                    <EmptyAndCreateComponent
                        title={"模型列表空空如也～"}
                        subTitle={"快去创建一个吧！"}
                        buttonText={"创建模型 +"}
                        onButtonClick={() => {
                            handleCreateModelClick()
                        }}
                    />
                </div>
            }
        </div>
    )
}
