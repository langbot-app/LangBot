"use client"
import {Modal} from "antd";
import {useState} from "react";
import CreateCardComponent from "@/app/infra/basic-component/create-card-component/CreateCardComponent";
import PipelineFormComponent from "./components/pipeline-form/PipelineFormComponent";


export default function PluginConfigPage() {
    const [modalOpen, setModalOpen] = useState<boolean>(false);
    const [isEditForm, setIsEditForm] = useState(false)


    return (
        <div className={``}>
            <Modal
                title={isEditForm ? "编辑流水线" : "创建流水线"}
                centered
                open={modalOpen}
                onOk={() => setModalOpen(false)}
                onCancel={() => setModalOpen(false)}
                width={700}
                footer={null}
            >
                    <PipelineFormComponent onFinish={() => {}} onCancel={() => {}}/>
            </Modal>

            <CreateCardComponent width={360} height={200} plusSize={90} onClick={() => {setModalOpen(true)}}/>
        </div>
    );
}
