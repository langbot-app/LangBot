"use client"
import {Modal} from "antd";
import {useState} from "react";
import CreateCardComponent from "@/app/infra/basic-component/create-card-component/CreateCardComponent";
import PipelineFormComponent from "./components/pipeline-form/PipelineFormComponent";
import {httpClient} from "@/app/infra/http/HttpClient";
import {PipelineCardVO} from "@/app/home/pipelines/components/pipeline-card/PipelineCardVO";


export default function PluginConfigPage() {
    const [modalOpen, setModalOpen] = useState<boolean>(false);
    const [isEditForm, setIsEditForm] = useState(false)
    const [pipelineList, setPipelineList] = useState([])


    function getPipelines() {
        httpClient.getPipelines().then(value => {
            value.pipelines.map(pipeline => {
                return new PipelineCardVO({
                    createTime: pipeline.created_at,
                    description: pipeline.description,
                    id: pipeline.uuid,
                    name: pipeline.name,
                    version: pipeline.for_version
                })
            })
        }).catch(error => {
            // TODO toast
            console.log(error)
        })
    }

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
                    <PipelineFormComponent
                        onFinish={() => {
                            getPipelines()
                            setModalOpen(false)
                        }}
                        onCancel={() => {}}/>
            </Modal>

            <CreateCardComponent width={360} height={200} plusSize={90} onClick={() => {setModalOpen(true)}}/>
        </div>
    );
}
