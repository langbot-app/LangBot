import { useEffect, useState } from 'react';
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
import { IDynamicFormItemSchema } from '@/app/infra/entities/form/dynamic';
import DynamicFormItemComponent from '@/app/home/components/dynamic-form/DynamicFormItemComponent';
import { i18nObj } from '@/i18n/I18nProvider';

/**
 * N8n认证表单组件
 * 根据选择的认证类型动态显示相应的表单项
 */
export default function N8nAuthFormComponent({
  itemConfigList,
  onSubmit,
  initialValues,
}: {
  itemConfigList: IDynamicFormItemSchema[];
  onSubmit?: (val: object) => unknown;
  initialValues?: Record<string, string>;
}) {
  // 当前选择的认证类型
  const [authType, setAuthType] = useState<string>(
    initialValues?.['auth-type'] || 'none',
  );

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
  useEffect(() => {
    if (initialValues) {
      // 合并默认值和初始值
      const mergedValues = itemConfigList.reduce(
        (acc, item) => {
          acc[item.name] = initialValues[item.name] ?? item.default;
          return acc;
        },
        {} as Record<string, string>,
      );

      Object.entries(mergedValues).forEach(([key, value]) => {
        form.setValue(key as keyof FormValues, value);
      });

      // 更新认证类型
      setAuthType((mergedValues['auth-type'] as string) || 'none');
    }
  }, [initialValues, form, itemConfigList]);

  // 监听表单值变化
  useEffect(() => {
    const subscription = form.watch((value, { name }) => {
      // 如果认证类型变化，更新状态
      if (name === 'auth-type') {
        setAuthType(value['auth-type'] as string);
      }

      // 获取完整的表单值，确保包含所有默认值
      const formValues = form.getValues();
      const finalValues = itemConfigList.reduce(
        (acc, item) => {
          acc[item.name] = formValues[item.name] ?? item.default;
          return acc;
        },
        {} as Record<string, string>,
      );

      onSubmit?.(finalValues);
    });
    return () => subscription.unsubscribe();
  }, [form, onSubmit, itemConfigList]);

  // 根据认证类型过滤表单项
  const filteredConfigList = itemConfigList.filter((config) => {
    // 始终显示webhook-url、auth-type、timeout和output-key
    if (
      ['webhook-url', 'auth-type', 'timeout', 'output-key'].includes(
        config.name,
      )
    ) {
      return true;
    }

    // 根据认证类型显示相应的表单项
    if (authType === 'basic' && config.name.startsWith('basic-')) {
      return true;
    }
    if (authType === 'jwt' && config.name.startsWith('jwt-')) {
      return true;
    }
    if (authType === 'header' && config.name.startsWith('header-')) {
      return true;
    }

    return false;
  });

  return (
    <Form {...form}>
      <div className="space-y-4">
        {filteredConfigList.map((config) => (
          <FormField
            key={config.id}
            control={form.control}
            name={config.name as keyof FormValues}
            render={({ field }) => (
              <FormItem>
                <FormLabel>
                  {i18nObj(config.label)}{' '}
                  {config.required && <span className="text-red-500">*</span>}
                </FormLabel>
                <FormControl>
                  <DynamicFormItemComponent config={config} field={field} />
                </FormControl>
                {config.description && (
                  <p className="text-sm text-muted-foreground">
                    {i18nObj(config.description)}
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
