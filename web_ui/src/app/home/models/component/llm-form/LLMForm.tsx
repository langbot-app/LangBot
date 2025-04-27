import styles from "@/app/home/models/LLMConfig.module.css";
import {Button, Form, Input, Select, SelectProps, Space, Modal} from "antd";
import {ICreateLLMField} from "@/app/home/models/ICreateLLMField";
import {useEffect, useState} from "react";
import {IChooseRequesterEntity} from "@/app/home/models/component/llm-form/ChooseAdapterEntity";
import { httpClient } from "@/app/infra/http/HttpClient";
import {LLMModel} from "@/app/infra/api/api-types";
import {UUID} from "uuidjs";

export default function LLMForm({
    editMode,
    initLLMId,
    onFormSubmit,
    onFormCancel,
    onLLMDeleted,
}: {
    editMode: boolean;
    initLLMId?: string;
    onFormSubmit: (value: ICreateLLMField) => void;
    onFormCancel: (value: ICreateLLMField) => void;
    onLLMDeleted: () => void;
}) {
    const [form] = Form.useForm<ICreateLLMField>();
    const extraOptions: SelectProps['options'] = []
    const [initValue, setInitValue] = useState<ICreateLLMField>()
    const [showDeleteConfirmModal, setShowDeleteConfirmModal] = useState(false)
    const abilityOptions: SelectProps['options'] = [
        {
            label: '函数调用',
            value: 'func_call',
        },
        {
            label: '图像识别',
            value: 'vision',
        },
    ];
    const [requesterNameList, setRequesterNameList] = useState<IChooseRequesterEntity[]>([])

    useEffect(() => {
        initLLMModelFormComponent()
        if (editMode && initLLMId) {
            getLLMConfig(initLLMId).then(val => {
                form.setFieldsValue(val)
            })
        } else {
            form.resetFields()
        }
    }, [])

    async function initLLMModelFormComponent() {
        const requesterNameList = await httpClient.getProviderRequesters()
        setRequesterNameList(requesterNameList.requesters.map(item => {
            return {
                label: item.label.zh_CN,
                value: item.name
            }
        }))
    }

    async function getLLMConfig(id: string): Promise<ICreateLLMField> {

        const llmModel = await httpClient.getProviderLLMModel(id)

        let fakeExtraArgs = []
        const extraArgs = llmModel.model.extra_args as Record<string, string>
        for (const key in extraArgs) {
            fakeExtraArgs.push(`${key}:${extraArgs[key]}`)
        }
        return {
            name: llmModel.model.name,
            model_provider: llmModel.model.requester,
            url: llmModel.model.requester_config?.base_url,
            api_key: llmModel.model.api_keys[0],
            abilities: llmModel.model.abilities,
            extra_args: fakeExtraArgs,
        }
    }

    function handleFormSubmit(value: ICreateLLMField) {
        if (editMode) {
            // 暂不支持更改模型
            // onSaveEdit(value)
        } else {
            onCreateLLM(value)
        }
        form.resetFields()
    }

    function onSaveEdit(value: ICreateLLMField) {
        const requestParam: LLMModel = {
            uuid: UUID.generate(),
            name: value.name,
            description: "",
            requester: value.model_provider,
            requester_config: {
                "base_url": value.url,
                "timeout": 120
            },
            extra_args: value.extra_args,
            api_keys: [value.api_key],
            abilities: value.abilities,
            // created_at: 'Sun Apr 27 2025 21:56:35 GMT+0800',
            // updated_at: 'Sun Apr 27 2025 21:56:35 GMT+0800',
        };
        httpClient.createProviderLLMModel(requestParam).then(r => console.log(r))
    }

    function onCreateLLM(value: ICreateLLMField) {
        console.log("create llm", value)
        const requestParam: LLMModel = {
            uuid: UUID.generate(),
            name: value.name,
            description: "",
            requester: value.model_provider,
            requester_config: {
                "base_url": value.url,
                "timeout": 120
            },
            extra_args: value.extra_args,
            api_keys: [value.api_key],
            abilities: value.abilities,
            // created_at: 'Sun Apr 27 2025 21:56:35 GMT+0800',
            // updated_at: 'Sun Apr 27 2025 21:56:35 GMT+0800',
        };
        httpClient.createProviderLLMModel(requestParam).then(r => {
            onFormSubmit(value)
        })
    }

    function handleAbilitiesChange() {

    }

    function deleteModel() {
        if (initLLMId) {
            httpClient.deleteProviderLLMModel(initLLMId).then(res => {
                onLLMDeleted()
            })
        }
    }

    return (
        <div className={styles.modalContainer}>
            <Modal
                open={showDeleteConfirmModal}
                title={"删除确认"}
                onCancel={() => setShowDeleteConfirmModal(false)}
                footer={
                    <div
                        style={{
                            width: "170px",
                            display: "flex",
                            flexDirection: "row",
                            justifyContent: "space-between"
                        }}
                    >
                        <Button
                            danger
                            onClick={() => {
                                deleteModel()
                                setShowDeleteConfirmModal(false)
                            }}
                        >确认删除</Button>
                        <Button
                            onClick={() => {
                                setShowDeleteConfirmModal(false)
                            }}
                        >取消</Button>
                    </div>
                }

            >
                你确定要删除这个模型吗？
            </Modal>
            <Form
                form={form}
                labelCol={{span: 4}}
                wrapperCol={{span: 14}}
                layout='horizontal'
                initialValues={{
                    ...initValue
                }}
                onFinish={handleFormSubmit}
                clearOnDestroy={true}
                disabled={editMode}
            >
                <Form.Item<ICreateLLMField>
                    label={"模型名称"}
                    name={"name"}
                    rules={[{required: true, message: "该项为必填项哦～"}]}
                >
                    <Input
                        placeholder={"为自己的大模型取个好听的名字～"}
                        style={{width: 260}}
                    ></Input>
                </Form.Item>

                <Form.Item<ICreateLLMField>
                    label={"模型供应商"}
                    name={"model_provider"}
                    rules={[{required: true, message: "该项为必填项哦～"}]}
                >
                    <Select
                        style={{width: 120}}
                        onChange={() => {
                        }}
                        options={requesterNameList}
                    />
                </Form.Item>

                <Form.Item<ICreateLLMField>
                    label={"请求URL"}
                    name={"url"}
                    rules={[{required: true, message: "该项为必填项哦～"}]}
                >
                    <Input
                        placeholder="请求地址，一般是API提供商提供的URL"
                        style={{width: 500}}
                    ></Input>
                </Form.Item>

                <Form.Item<ICreateLLMField>
                    label={"API Key"}
                    name={"api_key"}
                    rules={[{required: true, message: "该项为必填项哦～"}]}
                >
                    <Input
                        placeholder="你的API Key"
                        style={{width: 500}}
                    ></Input>
                </Form.Item>


                <Form.Item<ICreateLLMField>
                    label={"开启能力"}
                    name={"abilities"}
                >
                    <Select
                        mode="tags"
                        style={{width: 500}}
                        placeholder="选择模型能力，输入回车可自定义能力"
                        onChange={handleAbilitiesChange}
                        options={abilityOptions}
                    />
                </Form.Item>

                <Form.Item<ICreateLLMField>
                    label={"其他参数"}
                    name={"extra_args"}
                >
                    <Select
                        mode="tags"
                        style={{width: 500}}
                        placeholder="输入后回车可自定义其他参数，例 key:value"
                        onChange={handleAbilitiesChange}
                        options={extraOptions}
                    />
                </Form.Item>

                <Form.Item
                    wrapperCol={{offset: 4, span: 14}}
                >
                    <Space>
                        {
                            !editMode &&
                            <Button type="primary" htmlType="submit">
                                提交
                            </Button>
                        }
                        {
                            editMode &&
                            <Button
                                color="danger"
                                variant="solid"
                                onClick={() => {setShowDeleteConfirmModal(true)}}
                                disabled={false}
                            >
                                删除
                            </Button>
                        }
                        <Button
                            htmlType="button"
                            onClick={() => {
                            onFormCancel(form.getFieldsValue())
                            }}
                            disabled={false}
                        >
                            取消
                        </Button>
                    </Space>
                </Form.Item>
            </Form>
        </div>

    )
}