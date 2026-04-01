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
import { normalizeDynamicFieldValue } from '@/app/home/components/dynamic-form/dynamicFormValueUtils';
import { extractI18nObject } from '@/i18n/I18nProvider';
import { useTranslation } from 'react-i18next';

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
  initialValues?: Record<string, unknown>;
  onFileUploaded?: (fileKey: string) => void;
  isEditing?: boolean;
  externalDependentValues?: Record<string, unknown>;
}) {
  const isInitialMount = useRef(true);
  const previousInitialValues = useRef(initialValues);
  const { t } = useTranslation();

  // Build a zod schema dynamically from the form item configuration.
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
      // Prefer initialValues, otherwise fall back to the schema default.
      const rawValue = initialValues?.[item.name] ?? item.default;
      return {
        ...acc,
        [item.name]: normalizeDynamicFieldValue(item, rawValue),
      };
    }, {} as FormValues),
  });

  // Update form values when initialValues changes.
  // Avoid resetting the form when parent state echoes back values emitted by this form itself.
  useEffect(() => {
    // On first mount, trust initialValues as the baseline snapshot.
    if (isInitialMount.current) {
      isInitialMount.current = false;
      previousInitialValues.current = initialValues;
      return;
    }

    // Only react when initialValues has changed materially.
    // Use JSON.stringify for a pragmatic deep comparison here.
    const hasRealChange =
      JSON.stringify(previousInitialValues.current) !==
      JSON.stringify(initialValues);

    if (initialValues && hasRealChange) {
      // Merge schema defaults with the incoming initial values.
      const mergedValues = itemConfigList.reduce(
        (acc, item) => {
          const rawValue = initialValues[item.name] ?? item.default;
          acc[item.name] = normalizeDynamicFieldValue(item, rawValue);
          return acc;
        },
        {} as Record<string, unknown>,
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

  const visibleItemConfigList = itemConfigList.filter((config) => {
    if (config.show_if) {
      const dependValue =
        watchedValues[config.show_if.field as keyof typeof watchedValues] !==
        undefined
          ? watchedValues[config.show_if.field as keyof typeof watchedValues]
          : externalDependentValues?.[config.show_if.field];

      if (
        config.show_if.operator === 'eq' &&
        dependValue !== config.show_if.value
      ) {
        return false;
      }
      if (
        config.show_if.operator === 'neq' &&
        dependValue === config.show_if.value
      ) {
        return false;
      }
      if (
        config.show_if.operator === 'in' &&
        Array.isArray(config.show_if.value) &&
        !config.show_if.value.includes(dependValue)
      ) {
        return false;
      }
    }
    return true;
  });

  // Watch form value changes and emit a normalized snapshot upward.
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
      {} as Record<string, unknown>,
    );
    onSubmitRef.current?.(initialFinalValues);

    // Update previousInitialValues to the emitted snapshot so that if the
    // parent writes these values back as new initialValues, the deep
    // comparison in the initialValues-sync useEffect won't detect a change
    // and won't trigger an infinite update loop.
    previousInitialValues.current = initialFinalValues as Record<
      string,
      unknown
    >;

    const subscription = form.watch(() => {
      const formValues = form.getValues();
      const finalValues = itemConfigList.reduce(
        (acc, item) => {
          acc[item.name] = formValues[item.name] ?? item.default;
          return acc;
        },
        {} as Record<string, unknown>,
      );
      onSubmitRef.current?.(finalValues);
      previousInitialValues.current = finalValues as Record<string, unknown>;
    });
    return () => subscription.unsubscribe();
  }, [form, itemConfigList]);

  return (
    <Form {...form}>
      <div className="space-y-4">
        {visibleItemConfigList.map((config, index) => {
          // All fields are disabled when editing (creation_settings are immutable)
          const isFieldDisabled = !!isEditing;
          const currentSection = config.section
            ? extractI18nObject(config.section)
            : '';
          const previousSection =
            index > 0 && visibleItemConfigList[index - 1].section
              ? extractI18nObject(visibleItemConfigList[index - 1].section!)
              : '';
          const showSectionHeader =
            Boolean(currentSection) && currentSection !== previousSection;

          return (
            <div key={config.id} className="space-y-4">
              {showSectionHeader && (
                <div className="border-t pt-4">
                  <h4 className="text-sm font-medium text-foreground">
                    {currentSection}
                  </h4>
                </div>
              )}
              <FormField
                control={form.control}
                name={config.name as keyof FormValues}
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>
                      {extractI18nObject(config.label)}{' '}
                      {config.required && (
                        <span className="text-red-500">*</span>
                      )}
                    </FormLabel>
                    <FormControl>
                      <div
                        className={
                          isFieldDisabled
                            ? 'pointer-events-none opacity-60'
                            : ''
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
            </div>
          );
        })}
      </div>
    </Form>
  );
}
