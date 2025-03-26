import {Form, Input, InputNumber, Select, Switch} from "antd";
import {DynamicFormItemType, IDynamicFormItemConfig} from "@/app/home/components/dynamic-form/DynamicFormItemConfig";

export default function DynamicFormItemComponent({
    config
}: {
    config: IDynamicFormItemConfig
}) {
    return (
        <Form.Item
            label={config.label.zh_CN}
            name={config.name}
            rules={[{required: config.required, message: "该项为必填项哦～"}]}
            initialValue={config.default}
        >
            {
                config.type === DynamicFormItemType.INT &&
                <InputNumber/>
            }

            {
                config.type === DynamicFormItemType.STRING &&
                <Input/>
            }

            {
                config.type === DynamicFormItemType.BOOLEAN &&
                <Switch defaultChecked/>
            }

            {
                config.type === DynamicFormItemType.STRING_ARRAY &&
                <Select options={[]}/>
            }
        </Form.Item>
    )

}