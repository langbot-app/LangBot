import {BotFormEntity, IBotFormEntity} from "@/app/home/bots/components/bot-form/BotFormEntity";
import {fetchAdapterList} from "@/app/home/mock-api/index"
import {Button, Form, Input, Select, Space} from "antd";
import {useEffect, useState} from "react";
import {IChooseAdapterEntity} from "@/app/home/bots/components/bot-form/ChooseAdapterEntity";
import {
    DynamicFormItemConfig,
    IDynamicFormItemConfig,
    parseDynamicFormItemType
} from "@/app/home/components/dynamic-form/DynamicFormItemConfig";
import {UUID} from 'uuidjs'
import DynamicFormComponent from "@/app/home/components/dynamic-form/DynamicFormComponent";
import {ICreateLLMField} from "@/app/home/models/ICreateLLMField";

export default function BotForm({
    initBotId,
    onFormSubmit,
    onFormCancel,
}: {
    initBotId?: string;
    onFormSubmit: (value: IBotFormEntity) => void;
    onFormCancel: (value: IBotFormEntity) => void;
}) {
    const [adapterNameToDynamicConfigMap, setAdapterNameToDynamicConfigMap] = useState(new Map<string, IDynamicFormItemConfig[]>())
    const [form] = Form.useForm<IBotFormEntity>();
    const [showDynamicForm, setShowDynamicForm] = useState<boolean>(false)
    const [dynamicForm] = Form.useForm();
    const [adapterNameList, setAdapterNameList] = useState<IChooseAdapterEntity[]>([])
    const [dynamicFormConfigList, setDynamicFormConfigList] = useState<IDynamicFormItemConfig[]>([])

    useEffect(() => {
        initBotFormComponent()
        if (initBotId) {
            onEditMode()
        } else {
            onCreateMode()
        }
    }, [])

    async function initBotFormComponent() {
        // 拉取adapter
        const rawAdapterList = await fetchAdapterList()
        // 初始化适配器选择列表
        setAdapterNameList(
            rawAdapterList.map(item => {
                return {
                    label: item.label.zh_CN,
                    value: item.name
                }
            })
        )
        // 初始化适配器表单map
        rawAdapterList.forEach(rawAdapter => {
            adapterNameToDynamicConfigMap.set(
                rawAdapter.name,
                rawAdapter.spec.config.map(item =>
                    new DynamicFormItemConfig({
                        default: item.default,
                        id: UUID.generate(),
                        label: item.label,
                        name: item.name,
                        required: item.required,
                        type: parseDynamicFormItemType(item.type)
                    })
                )
            )
        })
        // 拉取初始化表单信息
        if (initBotId) {
            getBotFieldById(initBotId).then(val => {
                form.setFieldsValue(val)
                handleAdapterSelect(val.adapter)
            })
        } else {
            form.resetFields()
        }
        setAdapterNameToDynamicConfigMap(adapterNameToDynamicConfigMap)
    }

    async function onCreateMode() {

    }

    function onEditMode() {

    }

    async function getBotFieldById(botId: string): Promise<IBotFormEntity> {
        return new BotFormEntity({
            adapter: "telegram",
            description: "模拟拉取bot",
            name: "模拟电报bot",
            adapter_config: {
                token: "aaabbbccc"
            },
        })
    }

    function handleAdapterSelect(adapterName: string) {
        if (adapterName) {
            console.log(adapterNameToDynamicConfigMap)
            const dynamicFormConfigList = adapterNameToDynamicConfigMap.get(adapterName)
            if (dynamicFormConfigList) {
                console.log(dynamicFormConfigList)
                setDynamicFormConfigList(dynamicFormConfigList)
            }
            setShowDynamicForm(true)
        } else {
            setShowDynamicForm(false)
        }
    }

    function handleSubmitButton() {
        form.submit()
    }

    function handleFormFinish(value: IBotFormEntity) {
        dynamicForm.submit()
    }

    // 只有通过外层固定表单验证才会走到这里，真正的提交逻辑在这里
    function onDynamicFormSubmit(value: object) {
        if (initBotId) {
            // 编辑提交
            console.log('submit edit', form.getFieldsValue() ,value)
        } else {
            // 创建提交
            console.log('submit create', form.getFieldsValue() ,value)
        }
        onFormSubmit(form.getFieldsValue())
        setShowDynamicForm(false)
        form.resetFields()
        dynamicForm.resetFields()

    }

    function handleSaveButton() {

    }

    return (
        <div>
            <Form
                form={form}
                labelCol={{span: 5}}
                wrapperCol={{span: 18}}
                layout='vertical'
                onFinish={handleFormFinish}
            >
                <Form.Item<IBotFormEntity>
                    label={"机器人名称"}
                    name={"name"}
                    rules={[{required: true, message: "该项为必填项哦～"}]}
                >
                    <Input
                        placeholder="为机器人取个好听的名字吧～"
                        style={{width: 260}}
                    ></Input>
                </Form.Item>

                <Form.Item<IBotFormEntity>
                    label={"描述"}
                    name={"description"}
                    rules={[{required: true, message: "该项为必填项哦～"}]}
                >
                    <Input
                        placeholder="简单描述一下这个机器人"
                    ></Input>
                </Form.Item>

                <Form.Item<IBotFormEntity>
                    label={"平台/适配器选择"}
                    name={"adapter"}
                    rules={[{required: true, message: "该项为必填项哦～"}]}
                >
                    <Select
                        style={{width: 220}}
                        onChange={(value) => {
                            handleAdapterSelect(value)
                        }}
                        options={adapterNameList}
                    />
                </Form.Item>
            </Form>
            {
                showDynamicForm &&
                <DynamicFormComponent
                    form={dynamicForm}
                    itemConfigList={dynamicFormConfigList}
                    onSubmit={onDynamicFormSubmit}
                />
            }
            <Space>
                {
                    !initBotId &&
                    <Button
                        type="primary"
                        htmlType="button"
                        onClick={handleSubmitButton}
                    >
                        提交
                    </Button>
                }
                {
                    initBotId &&
                    <Button
                        type="primary"
                        htmlType="submit"
                        onClick={handleSaveButton}
                    >
                        保存
                    </Button>
                }
                <Button htmlType="button" onClick={() => {
                    onFormCancel(form.getFieldsValue())
                }}>
                    取消
                </Button>
            </Space>
        </div>
    )
}