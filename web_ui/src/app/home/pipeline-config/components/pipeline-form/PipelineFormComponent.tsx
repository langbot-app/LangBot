import {Form, Button, Switch, Select, Input, InputNumber} from "antd";
import { CaretLeftOutlined, CaretRightOutlined } from '@ant-design/icons';
import {useState} from "react";
import styles from "./pipelineFormStyle.module.css"

export default function PipelineFormComponent({
    onFinish,
    onCancel,
}: {
    onFinish: () => void;
    onCancel: () => void;
}) {
    const [nowFormIndex, setNowFormIndex] = useState<number>(0)
    // 这里不好，可以改成enum等
    const formLabelList: FormLabel[] = [
        {label: "AI能力", name: "ai"},
        {label: "触发条件", name: "trigger"},
        {label: "安全能力", name: "safety"},
        {label: "输出处理", name: "output"},
    ]

    function getNowFormLabel() {
        return formLabelList[nowFormIndex]
    }


    function getPreFormLabel(): undefined | FormLabel {
        if (nowFormIndex !== undefined && nowFormIndex > 0) {
            return formLabelList[nowFormIndex - 1]
        } else {
            return undefined
        }
    }

    function getNextFormLabel(): undefined | FormLabel {
        if (nowFormIndex !== undefined && nowFormIndex < formLabelList.length - 1) {
            return formLabelList[nowFormIndex + 1]
        } else {
            return undefined
        }
    }

    function addFormLabelIndex() {
        if (nowFormIndex < formLabelList.length - 1) {
            setNowFormIndex(nowFormIndex + 1)
        }
    }

    function reduceFormLabelIndex() {
        if (nowFormIndex > 0) {
            setNowFormIndex(nowFormIndex - 1)
        }
    }

    return (
        <div
            style={{ maxHeight: '70vh', overflowY: 'auto' }}
        >
            <h1>
                {getNowFormLabel().label}
            </h1>
            {/*  AI能力表单 ai  */}
            <Form
                layout={"vertical"}
                style={{ display: getNowFormLabel().name === "ai" ? 'block' : 'none' }}
            >
                {/* Runner 配置区块 */}
                <div className={`${styles.formItemSubtitle}`}>运行器</div>
                <Form.Item
                    label="运行器"
                    name={["runner", "runner"]}
                    rules={[{ required: true }]}
                >
                    <Select
                        options={[
                            { label: "内置 Agent", value: "local-agent" },
                            { label: "Dify 服务 API", value: "dify-service-api" },
                            { label: "阿里云百炼平台 API", value: "dashscope-app-api" }
                        ]}
                    />
                </Form.Item>

                {/* 内置 Agent 配置区块 */}
                <div className={`${styles.formItemSubtitle}`}>配置内置Agent</div>
                {/*  TODO 这里要拉模型  */}
                <Form.Item
                    label="模型"
                    name={["local-agent", "model"]}
                    rules={[{ required: true }]}
                    tooltip="从模型库中选择"
                >
                    <Select
                        options={[]}
                        placeholder="请选择语言模型"
                        showSearch
                    />
                </Form.Item>
                <Form.Item
                    label="最大回合数"
                    name={["local-agent", "max-round"]}
                    rules={[{
                        required: true,
                    }]}
                >
                    <InputNumber
                        precision={0}
                    />
                </Form.Item>
                {/*  TODO 这里要做转换处理  */}
                <Form.Item
                    label="提示词"
                    name={["local-agent", "prompt"]}
                    rules={[{ required: true }]}
                    tooltip="按JSON格式输入"
                >
                    <Input.TextArea
                        rows={4}
                        placeholder={`示例结构：{ "role": "user", "content": "你好" } `}
                    />
                </Form.Item>

                {/* Dify 服务 API 区块 */}
                <div className={`${styles.formItemSubtitle}`}>配置Dify服务API</div>
                <Form.Item
                    label="基础 URL"
                    name={["dify-service-api", "base-url"]}
                    rules={[
                        { required: true },
                        { type: 'url', message: '请输入有效的URL地址' }
                    ]}
                >
                    <Input/>
                </Form.Item>
                <Form.Item
                    label="应用类型"
                    name={["dify-service-api", "app-type"]}
                    initialValue={"chat"}
                    rules={[{ required: true }]}
                >
                    <Select
                        options={[
                            { label: "聊天（包括Chatflow）", value: "chat" },
                            { label: "Agent", value: "agent" },
                            { label: "工作流", value: "workflow" }
                        ]}
                    />
                </Form.Item>
                <Form.Item
                    label="API 密钥"
                    name={["dify-service-api", "api-key"]}
                    rules={[{ required: true }]}
                >
                    <Input.Password visibilityToggle={false} />
                </Form.Item>
                <Form.Item
                    label="思维链转换"
                    name={["dify-service-api", "thinking-convert"]}
                    rules={[{ required: true }]}
                >
                    <Select
                        options={[
                            { label: "转换成 \<think\>...\<\/think\>", value: "plain" },
                            { label: "原始", value: "original" },
                            { label: "移除", value: "remove" }
                        ]}
                    />
                </Form.Item>

                {/* 阿里云百炼区块 */}
                <div className={`${styles.formItemSubtitle}`}>配置阿里云百炼平台 API</div>
                <Form.Item
                    label="应用类型"
                    name={["dashscope-app-api", "app-type"]}
                    rules={[{ required: true }]}
                >
                    <Select
                        options={[
                            { label: "Agent", value: "agent" },
                            { label: "工作流", value: "workflow" }
                        ]}
                    />
                </Form.Item>
                <Form.Item
                    label="API 密钥"
                    name={["dashscope-app-api", "api-key"]}
                    rules={[{ required: true }]}
                >
                    <Input.Password visibilityToggle={false} />
                </Form.Item>
                <Form.Item
                    label="应用 ID"
                    name={["dashscope-app-api", "app-id"]}
                    rules={[
                        { required: true },
                    ]}
                >
                    <Input />
                </Form.Item>
                <Form.Item
                    label="引用文本"
                    name={["dashscope-app-api", "references_quote"]}
                    initialValue={"参考资料来自:"}
                >
                    <Input.TextArea rows={2} />
                </Form.Item>
            </Form>

            {/*  触发条件表单 trigger */}
            <Form
                layout={"vertical"}
                style={{ display: getNowFormLabel().name === "trigger" ? 'block' : 'none' }}
            >
                {/* 群响应规则块 */}
                <Form.Item>
                    群响应规则
                </Form.Item>
                <Form.Item
                    label={"是否在消息@机器人时触发"}
                    name={["group-respond-rules", "at"]}
                    rules={[{ required: true }]}
                >
                    <Switch />
                </Form.Item>
                <Form.Item
                    label={"消息前缀"}
                    name={["group-respond-rules", "prefix"]}
                    rules={[{ required: true }]}
                >
                    <Select
                        options={[
                            { value: "\"type\": \"string\"", label: "\"type\": \"string\"" },
                        ]}
                    />
                </Form.Item>
                <Form.Item
                    label={"正则表达式"}
                    name={["group-respond-rules", "regexp"]}
                    rules={[{ required: true }]}
                >
                    <Select
                        mode="tags"
                        options={[]}
                    />
                </Form.Item>
                <Form.Item
                    label={"随机"}
                    name={["group-respond-rules", "random"]}
                    rules={[{ required: false }]}
                >
                    <InputNumber
                        max={1}
                        min={0}
                        step={0.05}
                    />
                </Form.Item>

                <Form.Item>
                    访问控制
                </Form.Item>
                <Form.Item
                    label={"模式"}
                    name={["access-control", "mode"]}
                    rules={[{ required: true }]}
                    tooltip={"访问控制模式"}
                >
                    <Select
                        options={[
                            {label: "黑名单", value: "blacklist"},
                            {label: "白名单", value: "Whitelist"},
                        ]}
                    />
                </Form.Item>

                <Form.Item
                    label={"黑名单"}
                    name={["access-control", "blacklist"]}
                    rules={[{ required: true }]}
                >
                    <Select
                        mode={"tags"}
                        options={[]}
                    />
                </Form.Item>

                <Form.Item
                    label={"白名单"}
                    name={["access-control", "whitelist"]}
                    rules={[{ required: true }]}
                >
                    <Select
                        mode={"tags"}
                        options={[]}
                    />
                </Form.Item>

                <Form.Item
                    label={"消息忽略规则"}
                >
                </Form.Item>

                <Form.Item
                    label={"前缀"}
                    name={["ignore-rules", "whitelist"]}
                    rules={[{ required: true }]}
                    tooltip={"消息前缀"}
                >
                    <Select
                        mode={"tags"}
                        options={[]}
                    />
                </Form.Item>

                <Form.Item
                    label={"正则表达式"}
                    name={["ignore-rules", "regexp"]}
                    rules={[{ required: true }]}
                    tooltip={"消息正则表达式"}
                >
                    <Select
                        mode={"tags"}
                        options={[]}
                    />
                </Form.Item>
            </Form>

            {/*  安全控制表单 safety  */}
            <Form
                layout={"vertical"}
                style={{ display: getNowFormLabel().name === "safety" ? 'block' : 'none' }}
            >
                {/* 内容过滤块 content-filter */}
                <Form.Item
                    label={"检查范围"}
                    name={["content-filter", "scope"]}
                    rules={[{ required: true }]}
                >
                    <Select
                        options={[
                            {label: "全部", value: "all"},
                            {label: "传入消息（用户消息）", value: "income-msg"},
                            {label: "传出消息（机器人消息）", value: "output-msg"},
                        ]}
                    />
                </Form.Item>

                <Form.Item
                    label={"检查敏感词"}
                    name={["content-filter", "check-sensitive-words"]}
                    rules={[{ required: true }]}
                >
                    <Switch/>
                </Form.Item>

                {/* 速率限制块 rate-limit */}

                <Form.Item
                    label={"窗口长度（秒）"}
                    name={["rate-limit", "window-length"]}
                    rules={[{ required: true }]}
                    initialValue={60}
                >
                    <InputNumber></InputNumber>
                </Form.Item>
                <Form.Item
                    label={"限制次数"}
                    name={["rate-limit", "limitation"]}
                    rules={[{ required: true }]}
                    initialValue={60}
                >
                    <InputNumber/>
                </Form.Item>
                <Form.Item
                    label={"策略"}
                    name={["rate-limit", "strategy"]}
                    rules={[{ required: true }]}
                    initialValue={"drop"}
                >
                    <Select
                        options={[
                            {label: "丢弃", value: "drop"},
                            {label: "等待", value: "wait"},
                        ]}
                    />
                </Form.Item>

            </Form>

            {/*  输出处理控制表单 output  */}
            <Form
                layout={"vertical"}
                style={{ display: getNowFormLabel().name === "output" ? 'block' : 'none' }}
            >
                {/* 长文本处理区块 */}
                <Form.Item label="长文本处理" />
                <Form.Item
                    label="阈值"
                    name={["long-text-processing", "threshold"]}
                    rules={[{ required: true }]}
                >
                    <InputNumber />
                </Form.Item>
                <Form.Item
                    label="策略"
                    name={["long-text-processing", "strategy"]}
                    rules={[{ required: true }]}
                >
                    <Select
                        options={[
                            { label: "转发消息组件", value: "forward" },
                            { label: "转换为图片", value: "image" }
                        ]}
                    />
                </Form.Item>
                <Form.Item
                    label="字体路径"
                    name={["long-text-processing", "font-path"]}
                    rules={[{ required: true }]}
                >
                    <Input />
                </Form.Item>

                {/* 强制延迟区块 */}
                <Form.Item label="强制延迟" />
                <Form.Item
                    label="最小秒数"
                    name={["force-delay", "min"]}
                    rules={[{ required: true }]}
                >
                    <InputNumber />
                </Form.Item>
                <Form.Item
                    label="最大秒数"
                    name={["force-delay", "max"]}
                    rules={[{ required: true }]}
                >
                    <InputNumber />
                </Form.Item>

                {/* 杂项区块 */}
                <Form.Item label="杂项" />
                <Form.Item
                    label="不输出异常信息给用户"
                    name={["misc", "hide-exception"]}
                    rules={[{ required: true }]}
                    valuePropName="checked"
                >
                    <Switch />
                </Form.Item>
                <Form.Item
                    label="在回复中@发送者"
                    name={["misc", "at-sender"]}
                    rules={[{ required: true }]}
                    valuePropName="checked"
                >
                    <Switch />
                </Form.Item>
                <Form.Item
                    label="引用原文"
                    name={["misc", "quote-origin"]}
                    rules={[{ required: true }]}
                    valuePropName="checked"
                >
                    <Switch />
                </Form.Item>
                <Form.Item
                    label="跟踪函数调用"
                    name={["misc", "track-function-calls"]}
                    rules={[{ required: true }]}
                    valuePropName="checked"
                >
                    <Switch />
                </Form.Item>
            </Form>

            <div className={`${styles.changeFormButtonGroupContainer}`}>
                <Button
                    type="primary"
                    icon={<CaretLeftOutlined/>}
                    onClick={reduceFormLabelIndex}
                    disabled={!getPreFormLabel()}
                >
                    {getPreFormLabel()?.label || "暂无更多"}
                </Button>
                <Button
                    type="primary"
                    icon={<CaretRightOutlined />}
                    onClick={addFormLabelIndex}
                    disabled={!getNextFormLabel()}
                    iconPosition={"end"}
                >
                    {getNextFormLabel()?.label || "暂无更多"}
                </Button>
            </div>

        </div>
    )
}

enum PipelineFormRoute {

}

interface FormPageLabel {
    formIndex: number,
    formName: string,
    formLabel: string,
}

interface FormLabel {
    label: string,
    name: string,
}
