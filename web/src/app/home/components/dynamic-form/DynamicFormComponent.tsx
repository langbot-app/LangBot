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
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/utils';

export default function DynamicFormComponent({
  itemConfigList,
  onSubmit,
  initialValues,
  onFileUploaded,
  isEditing,
  externalDependentValues,
}: {
  itemConfigList: IDynamicFormItemSchema[];
  onSubmit?: (val: object) => unknown;
  initialValues?: Record<string, object>;
  onFileUploaded?: (fileKey: string) => void;
  isEditing?: boolean;
  externalDependentValues?: Record<string, unknown>;
}) {
  const isInitialMount = useRef(true);
  const previousInitialValues = useRef(initialValues);
  const { t } = useTranslation();

  // Normalize a form value according to its field type.
  // This ensures legacy/malformed data (e.g. a plain string for
  // model-fallback-selector) is coerced to the expected shape
  // so that downstream components never crash.
  const normalizeFieldValue = (
    item: IDynamicFormItemSchema,
    value: unknown,
  ): unknown => {
    if (item.type === 'model-fallback-selector') {
      if (value != null && typeof value === 'object' && !Array.isArray(value)) {
        const obj = value as Record<string, unknown>;
        return {
          primary: typeof obj.primary === 'string' ? obj.primary : '',
          fallbacks: Array.isArray(obj.fallbacks)
            ? (obj.fallbacks as unknown[]).filter(
                (v): v is string => typeof v === 'string',
              )
            : [],
        };
      }
      // Legacy string format or any other unexpected type
      return {
        primary: typeof value === 'string' ? value : '',
        fallbacks: [],
      };
    }
    if (item.type === 'prompt-editor') {
      if (Array.isArray(value)) {
        return value;
      }
      // Default to a single empty system prompt entry
      return [{ role: 'system', content: '' }];
    }
    return value;
  };

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
          case 'embedding-model-selector':
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
          case 'model-fallback-selector':
            fieldSchema = z.object({
              primary: z.string(),
              fallbacks: z.array(z.string()),
            });
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
          fieldSchema = fieldSchema.min(1, {
            message: t('common.fieldRequired'),
          });
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
      const rawValue = initialValues?.[item.name] ?? item.default;
      return {
        ...acc,
        [item.name]: normalizeFieldValue(item, rawValue),
      };
    }, {} as FormValues),
  });

  // 当 initialValues 变化时更新表单值
  // 但要避免因为内部表单更新触发的 onSubmit 导致的 initialValues 变化而重新设置表单
  useEffect(() => {
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
          const rawValue = initialValues[item.name] ?? item.default;
          acc[item.name] = normalizeFieldValue(item, rawValue) as object;
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

  // Get reactive form values for conditional rendering
  const watchedValues = form.watch();

  // Stable ref for onSubmit to avoid re-triggering the effect when the
  // parent passes a new closure on every render.
  const onSubmitRef = useRef(onSubmit);
  onSubmitRef.current = onSubmit;

  // 监听表单值变化
  useEffect(() => {
    // Emit initial form values immediately so the parent always has a valid snapshot,
    // even if the user saves without modifying any field.
    // form.watch(callback) only fires on subsequent changes, not on mount.
    const formValues = form.getValues();
    const initialFinalValues = itemConfigList.reduce(
      (acc, item) => {
        acc[item.name] = formValues[item.name] ?? item.default;
        return acc;
      },
      {} as Record<string, object>,
    );
    onSubmitRef.current?.(initialFinalValues);

    // Update previousInitialValues to the emitted snapshot so that if the
    // parent writes these values back as new initialValues, the deep
    // comparison in the initialValues-sync useEffect won't detect a change
    // and won't trigger an infinite update loop.
    previousInitialValues.current = initialFinalValues as Record<
      string,
      object
    >;

    const subscription = form.watch(() => {
      const formValues = form.getValues();
      const finalValues = itemConfigList.reduce(
        (acc, item) => {
          acc[item.name] = formValues[item.name] ?? item.default;
          return acc;
        },
        {} as Record<string, object>,
      );
      onSubmitRef.current?.(finalValues);
      previousInitialValues.current = finalValues as Record<string, object>;
    });
    return () => subscription.unsubscribe();
  }, [form, itemConfigList]);

  return (
    <Form {...form}>
      <div className="space-y-4">
        {itemConfigList.map((config) => {
          if (config.show_if) {
            const dependValue =
              watchedValues[
                config.show_if.field as keyof typeof watchedValues
              ] !== undefined
                ? watchedValues[
                    config.show_if.field as keyof typeof watchedValues
                  ]
                : externalDependentValues?.[config.show_if.field];

            if (
              config.show_if.operator === 'eq' &&
              dependValue !== config.show_if.value
            ) {
              return null;
            }
            if (
              config.show_if.operator === 'neq' &&
              dependValue === config.show_if.value
            ) {
              return null;
            }
            if (
              config.show_if.operator === 'in' &&
              Array.isArray(config.show_if.value) &&
              !config.show_if.value.includes(dependValue)
            ) {
              return null;
            }
          }

          // All fields are disabled when editing (creation_settings are immutable)
          const isFieldDisabled = !!isEditing;

          // Boolean fields use a special inline layout
          if (config.type === 'boolean') {
            return (
              <FormField
                key={config.id}
                control={form.control}
                name={config.name as keyof FormValues}
                render={({ field }) => (
                  <FormItem>
                    <div
                      className={cn(
                        'flex flex-row items-center justify-between rounded-lg border p-4 max-w-2xl',
                        isFieldDisabled && 'pointer-events-none opacity-60',
                      )}
                    >
                      <div className="space-y-0.5">
                        <FormLabel className="text-base">
                          {extractI18nObject(config.label)}
                        </FormLabel>
                        {config.description && (
                          <p className="text-sm text-muted-foreground">
                            {extractI18nObject(config.description)}
                          </p>
                        )}
                      </div>
                      <FormControl>
                        <DynamicFormItemComponent
                          config={config}
                          field={field}
                          onFileUploaded={onFileUploaded}
                        />
                      </FormControl>
                    </div>
                    <FormMessage />
                  </FormItem>
                )}
              />
            );
          }

          return (
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
                    <div
                      className={
                        isFieldDisabled ? 'pointer-events-none opacity-60' : ''
                      }
                    >
                      <DynamicFormItemComponent
                        config={config}
                        field={field}
                        onFileUploaded={onFileUploaded}
                      />
                    </div>
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
          );
        })}
      </div>
    </Form>
  );
}
