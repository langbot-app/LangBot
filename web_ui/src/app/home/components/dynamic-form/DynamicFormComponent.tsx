import {IDynamicFormItemConfig} from "@/app/home/components/dynamic-form/DynamicFormItemConfig";
import {Form, FormInstance} from "antd";
import DynamicFormItemComponent from "@/app/home/components/dynamic-form/DynamicFormItemComponent";

export default function DynamicFormComponent({
    form,
    itemConfigList,
    onSubmit,
}: {
    form: FormInstance<object>
    itemConfigList: IDynamicFormItemConfig[]
    onSubmit?: (val: object) => unknown
}) {
    return (
        <Form
            form={form}
            onFinish={onSubmit}
            layout={"vertical"}
        >
            {
                itemConfigList.map(config =>
                    <DynamicFormItemComponent
                        key={config.id}
                        config={config}
                    />
                )
            }
        </Form>
    )
}