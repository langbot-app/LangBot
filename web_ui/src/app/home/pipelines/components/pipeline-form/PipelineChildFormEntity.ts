import {DynamicFormItemConfig} from "@/app/home/components/dynamic-form/DynamicFormItemConfig";

export interface IPipelineChildFormEntity {
    name: string;
    label: string;
    formItems: DynamicFormItemConfig[]
}

export class PipelineChildFormEntity implements IPipelineChildFormEntity {
    formItems: DynamicFormItemConfig[];
    label: string;
    name: string;

    constructor(props: IPipelineChildFormEntity) {
        this.form = props.form;
        this.label = props.label;
        this.name = props.name;
        this.formItems = props.formItems;
    }
}