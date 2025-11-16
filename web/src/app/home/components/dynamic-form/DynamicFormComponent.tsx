import { IDynamicFormItemSchema } from '@/app/infra/entities/form/dynamic';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import DynamicFormItemComponent from '@/app/home/components/dynamic-form/DynamicFormItemComponent';
import { useEffect, useRef } from 'react';
import { extractI18nObject } from '@/i18n/I18nProvider';

export default function DynamicFormComponent({
  itemConfigList,
  onSubmit,
  initialValues,
  onFileUploaded,
}: {
  itemConfigList: IDynamicFormItemSchema[];
  onSubmit?: (val: object) => unknown;
  initialValues?: Record<string, object>;
  onFileUploaded?: (fileKey: string) => void;
}) {
  const isInitialMount = useRef(true);
  const previousInitialValues = useRef(initialValues);

  // 根据 itemConfigList 动态生成 zod schema
  const formSchema = z.object(
    itemConfigList.reduce(
      (acc, item) => {
        let fieldSchema;
        switch (item.type) {
          case 'integer':
            fieldSchema = z.number();
            break;
          case 'float':
            fieldSchema = z.number();
            break;
          case 'boolean':
            fieldSchema = z.boolean();
            break;
          case 'string':
            fieldSchema = z.string();
            break;
          case 'array[string]':
            fieldSchema = z.array(z.string());
            break;
          case 'select':
            fieldSchema = z.string();
            break;
          case 'llm-model-selector':
            fieldSchema = z.string();
            break;
          case 'knowledge-base-selector':
            fieldSchema = z.string();
            break;
          case 'knowledge-base-multi-selector':
            fieldSchema = z.array(z.string());
            break;
          case 'bot-selector':
            fieldSchema = z.string();
            break;
          case 'prompt-editor':
            fieldSchema = z.array(
              z.object({
                content: z.string(),
                role: z.string(),
              }),
            );
            break;
          default:
            fieldSchema = z.string();
        }

        if (
          item.required &&
          (fieldSchema instanceof z.ZodString ||
            fieldSchema instanceof z.ZodArray)
        ) {
          fieldSchema = fieldSchema.min(1, { message: '此字段为必填项' });
        }

        return {
          ...acc,
          [item.name]: fieldSchema,
        };
      },
      {} as Record<string, z.ZodTypeAny>,
    ),
  );

  type FormValues = z.infer<typeof formSchema>;

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: itemConfigList.reduce((acc, item) => {
      // 优先使用 initialValues，如果没有则使用默认值
      const value = initialValues?.[item.name] ?? item.default;
      return {
        ...acc,
        [item.name]: value,
      };
    }, {} as FormValues),
  });

  // 当 initialValues 变化时更新表单值
  // 但要避免因为内部表单更新触发的 onSubmit 导致的 initialValues 变化而重新设置表单
  useEffect(() => {
    console.log('initialValues', initialValues);

    // 首次挂载时，使用 initialValues 初始化表单
    if (isInitialMount.current) {
      isInitialMount.current = false;
      previousInitialValues.current = initialValues;
      return;
    }

    // 检查 initialValues 是否真的发生了实质性变化
    // 使用 JSON.stringify 进行深度比较
    const hasRealChange =
      JSON.stringify(previousInitialValues.current) !==
      JSON.stringify(initialValues);

    if (initialValues && hasRealChange) {
      // 合并默认值和初始值
      const mergedValues = itemConfigList.reduce(
        (acc, item) => {
          acc[item.name] = initialValues[item.name] ?? item.default;
          return acc;
        },
        {} as Record<string, object>,
      );

      Object.entries(mergedValues).forEach(([key, value]) => {
        form.setValue(key as keyof FormValues, value);
      });

      previousInitialValues.current = initialValues;
    }
  }, [initialValues, form, itemConfigList]);

  // 监听表单值变化
  useEffect(() => {
    const subscription = form.watch(() => {
      // 获取完整的表单值，确保包含所有默认值
      const formValues = form.getValues();
      console.log('formValues', formValues);
      const finalValues = itemConfigList.reduce(
        (acc, item) => {
          acc[item.name] = formValues[item.name] ?? item.default;
          return acc;
        },
        {} as Record<string, object>,
      );
      console.log('finalValues', finalValues);
      onSubmit?.(finalValues);
    });
    return () => subscription.unsubscribe();
  }, [form, onSubmit, itemConfigList]);

  return (
    <Form {...form}>
      <div className="space-y-4">
        {itemConfigList.map((config) => (
          <FormField
            key={config.id}
            control={form.control}
            name={config.name as keyof FormValues}
            render={({ field }) => (
              <FormItem>
                <FormLabel>
                  {extractI18nObject(config.label)}{' '}
                  {config.required && <span className="text-red-500">*</span>}
                </FormLabel>
                <FormControl>
                  <DynamicFormItemComponent
                    config={config}
                    field={field}
                    onFileUploaded={onFileUploaded}
                  />
                </FormControl>
                {config.description && (
                  <p className="text-sm text-muted-foreground">
                    {extractI18nObject(config.description)}
                  </p>
                )}
                <FormMessage />
              </FormItem>
            )}
          />
        ))}
      </div>
    </Form>
  );
}
