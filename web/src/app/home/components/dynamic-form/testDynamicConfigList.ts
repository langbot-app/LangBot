import {
  DynamicFormItemType,
  IDynamicFormItemSchema,
} from '@/app/infra/entities/form/dynamic';
import { DynamicFormItemConfig } from '@/app/home/components/dynamic-form/DynamicFormItemConfig';

export const testDynamicConfigList: IDynamicFormItemSchema[] = [
  new DynamicFormItemConfig({
    default: '',
    id: '111',
    label: {
      zh_Hans: '测试字段string',
      en_US: 'eng test',
    },
    name: 'string_test',
    required: false,
    type: DynamicFormItemType.STRING,
  }),
  new DynamicFormItemConfig({
    default: '',
    id: '222',
    label: {
      zh_Hans: '测试字段int',
      en_US: 'int eng test',
    },
    name: 'int_test',
    required: true,
    type: DynamicFormItemType.INT,
  }),
  new DynamicFormItemConfig({
    default: '',
    id: '333',
    label: {
      zh_Hans: '测试字段boolean',
      en_US: 'boolean eng test',
    },
    name: 'boolean_test',
    required: false,
    type: DynamicFormItemType.BOOLEAN,
  }),
];
