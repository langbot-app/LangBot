import styles from "@/app/home/models/LLMConfig.module.css";
import {Button, Form, Input, Select, SelectProps, Space} from "antd";
import {ICreateLLMField} from "@/app/home/models/ICreateLLMField";
import {useEffect, useState} from "react";

export default function LLMForm({
    editMode,
    initLLMId,
    onFormSubmit,
    onFormCancel,
}: {
    editMode: boolean;
    initLLMId?: string;
    onFormSubmit: (value: ICreateLLMField) => void;
    onFormCancel: (value: ICreateLLMField) => void;
}) {
    const [form] = Form.useForm<ICreateLLMField>();
    const extraOptions: SelectProps['options'] = []
    const [initValue, setInitValue] = useState<ICreateLLMField>()
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
    useEffect(() => {
        if (editMode && initLLMId) {
            getLLMConfig(initLLMId).then(val => {
                form.setFieldsValue(val)
            })
        } else {
            form.resetFields()
        }
    })

    async function getLLMConfig(id: string): Promise<ICreateLLMField> {
        return {
            name: id,
            model_provider: "OpenAI",
            url: "www.aaa.com",
            api_key: "",
            abilities: [],
            extra_args: [],
        }
    }

    function handleFormSubmit(value: ICreateLLMField) {
        if (editMode) {
            onSaveEdit(value)
        } else {
            onCreateLLM(value)
        }
        onFormSubmit(value)
        form.resetFields()
    }

    function onSaveEdit(value: ICreateLLMField) {
        console.log("edit save", value)
    }

    function onCreateLLM(value: ICreateLLMField) {
        console.log("create llm", value)
    }

    function handleAbilitiesChange() {

    }
    return (
        <div className={styles.modalContainer}>
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
                        options={[
                            {value: 'OpenAI', label: 'OpenAI'},
                            {value: 'OLAMA', label: 'OLAMA'},
                            {value: 'DeepSeek', label: 'DeepSeek'},
                        ]}
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
                            <Button type="primary" htmlType="submit">
                                保存
                            </Button>
                        }
                        <Button htmlType="button" onClick={() => {
                            onFormCancel(form.getFieldsValue())
                        }}>
                            取消
                        </Button>
                    </Space>
                </Form.Item>
            </Form>
        </div>

    )
}