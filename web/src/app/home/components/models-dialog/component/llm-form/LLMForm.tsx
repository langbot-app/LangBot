import { useEffect, useState } from 'react';
import { httpClient } from '@/app/infra/http/HttpClient';
import { ModelProvider } from '@/app/infra/entities/api';

import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { useTranslation } from 'react-i18next';

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import { toast } from 'sonner';
import { extractI18nObject } from '@/i18n/I18nProvider';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { AlertCircle } from 'lucide-react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

const getFormSchema = (t: (key: string) => string) =>
  z.object({
    name: z.string().min(1, { message: t('models.modelNameRequired') }),
    provider_uuid: z.string().optional(),
    // New provider fields
    new_provider_requester: z.string().optional(),
    new_provider_url: z.string().optional(),
    new_provider_api_key: z.string().optional(),
    abilities: z.array(z.string()),
    extra_args: z
      .array(
        z.object({
          key: z.string(),
          type: z.enum(['string', 'number', 'boolean']),
          value: z.string(),
        }),
      )
      .optional(),
  });

interface LLMFormProps {
  editMode: boolean;
  initLLMId?: string;
  providers: ModelProvider[];
  onFormSubmit: () => void;
  onFormCancel: () => void;
  onLLMDeleted: () => void;
}

export default function LLMForm({
  editMode,
  initLLMId,
  providers,
  onFormSubmit,
  onFormCancel,
  onLLMDeleted,
}: LLMFormProps) {
  const { t } = useTranslation();
  const formSchema = getFormSchema(t);

  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: '',
      provider_uuid: '',
      new_provider_requester: '',
      new_provider_url: '',
      new_provider_api_key: '',
      abilities: [],
      extra_args: [],
    },
  });

  const [extraArgs, setExtraArgs] = useState<
    { key: string; type: 'string' | 'number' | 'boolean'; value: string }[]
  >([]);
  const [showDeleteConfirmModal, setShowDeleteConfirmModal] = useState(false);
  const [modelTesting, setModelTesting] = useState(false);
  const [testErrorMessage, setTestErrorMessage] = useState<string | null>(null);
  const [providerMode, setProviderMode] = useState<'existing' | 'new'>(
    'existing',
  );

  const [requesterList, setRequesterList] = useState<
    { label: string; value: string; category: string; defaultUrl: string }[]
  >([]);

  const abilityOptions = [
    { label: t('models.visionAbility'), value: 'vision' },
    { label: t('models.functionCallAbility'), value: 'func_call' },
  ];

  useEffect(() => {
    loadRequesters();
    if (editMode && initLLMId) {
      loadModel(initLLMId);
    }
  }, [editMode, initLLMId]);

  async function loadRequesters() {
    const resp = await httpClient.getProviderRequesters('llm');
    setRequesterList(
      resp.requesters.map((item) => ({
        label: extractI18nObject(item.label),
        value: item.name,
        category: item.spec.provider_category || 'manufacturer',
        defaultUrl:
          item.spec.config
            .find((c) => c.name === 'base_url')
            ?.default?.toString() || '',
      })),
    );
  }

  async function loadModel(id: string) {
    const resp = await httpClient.getProviderLLMModel(id);
    const model = resp.model;

    form.setValue('name', model.name);
    form.setValue('provider_uuid', model.provider_uuid);
    form.setValue('abilities', model.abilities || []);

    if (model.extra_args) {
      const args = Object.entries(model.extra_args).map(([key, value]) => {
        let type: 'string' | 'number' | 'boolean' = 'string';
        if (typeof value === 'number') type = 'number';
        else if (typeof value === 'boolean') type = 'boolean';
        return { key, type, value: String(value) };
      });
      setExtraArgs(args);
      form.setValue('extra_args', args);
    }

    setProviderMode('existing');
  }

  function handleFormSubmit(values: z.infer<typeof formSchema>) {
    const extraArgsObj: Record<string, string | number | boolean> = {};
    values.extra_args?.forEach((arg) => {
      if (arg.type === 'number') extraArgsObj[arg.key] = Number(arg.value);
      else if (arg.type === 'boolean')
        extraArgsObj[arg.key] = arg.value === 'true';
      else extraArgsObj[arg.key] = arg.value;
    });

    const modelData: Record<string, unknown> = {
      name: values.name,
      abilities: values.abilities,
      extra_args: extraArgsObj,
    };

    if (providerMode === 'existing' && values.provider_uuid) {
      modelData.provider_uuid = values.provider_uuid;
    } else if (providerMode === 'new') {
      modelData.provider = {
        requester: values.new_provider_requester,
        base_url: values.new_provider_url,
        api_keys: values.new_provider_api_key
          ? [values.new_provider_api_key]
          : [],
      };
    }

    if (editMode && initLLMId) {
      updateModel(initLLMId, modelData);
    } else {
      createModel(modelData);
    }
  }

  async function createModel(data: Record<string, unknown>) {
    try {
      await httpClient.createProviderLLMModel(data as never);
      toast.success(t('models.createSuccess'));
      onFormSubmit();
    } catch (err) {
      toast.error(t('models.createError') + (err as Error).message);
    }
  }

  async function updateModel(id: string, data: Record<string, unknown>) {
    try {
      await httpClient.updateProviderLLMModel(id, data as never);
      toast.success(t('models.saveSuccess'));
      onFormSubmit();
    } catch (err) {
      toast.error(t('models.saveError') + (err as Error).message);
    }
  }

  async function deleteModel() {
    if (!initLLMId) return;
    try {
      await httpClient.deleteProviderLLMModel(initLLMId);
      toast.success(t('models.deleteSuccess'));
      onLLMDeleted();
    } catch (err) {
      toast.error(t('models.deleteError') + (err as Error).message);
    }
  }

  async function testModel() {
    setModelTesting(true);
    setTestErrorMessage(null);

    const values = form.getValues();
    const extraArgsObj: Record<string, string | number | boolean> = {};
    values.extra_args?.forEach((arg) => {
      if (arg.type === 'number') extraArgsObj[arg.key] = Number(arg.value);
      else if (arg.type === 'boolean')
        extraArgsObj[arg.key] = arg.value === 'true';
      else extraArgsObj[arg.key] = arg.value;
    });

    let provider: Record<string, unknown>;
    if (providerMode === 'existing' && values.provider_uuid) {
      const p = providers.find((p) => p.uuid === values.provider_uuid);
      provider = {
        requester: p?.requester || '',
        base_url: p?.base_url || '',
        api_keys: p?.api_keys || [],
      };
    } else {
      provider = {
        requester: values.new_provider_requester,
        base_url: values.new_provider_url,
        api_keys: values.new_provider_api_key
          ? [values.new_provider_api_key]
          : [],
      };
    }

    try {
      await httpClient.testLLMModel('_', {
        uuid: '',
        name: values.name,
        provider_uuid: '',
        provider,
        abilities: values.abilities,
        extra_args: extraArgsObj,
      } as never);
      toast.success(t('models.testSuccess'));
    } catch (err) {
      setTestErrorMessage((err as Error).message || t('models.testError'));
    } finally {
      setModelTesting(false);
    }
  }

  const addExtraArg = () => {
    const newArgs = [
      ...extraArgs,
      { key: '', type: 'string' as const, value: '' },
    ];
    setExtraArgs(newArgs);
    form.setValue('extra_args', newArgs);
  };

  const updateExtraArg = (
    index: number,
    field: 'key' | 'type' | 'value',
    value: string,
  ) => {
    const newArgs = [...extraArgs];
    newArgs[index] = { ...newArgs[index], [field]: value };
    setExtraArgs(newArgs);
    form.setValue('extra_args', newArgs);
  };

  const removeExtraArg = (index: number) => {
    const newArgs = extraArgs.filter((_, i) => i !== index);
    setExtraArgs(newArgs);
    form.setValue('extra_args', newArgs);
  };

  return (
    <div>
      <Dialog
        open={showDeleteConfirmModal}
        onOpenChange={setShowDeleteConfirmModal}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('common.confirmDelete')}</DialogTitle>
          </DialogHeader>
          <DialogDescription>
            {t('models.deleteConfirmation')}
          </DialogDescription>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowDeleteConfirmModal(false)}
            >
              {t('common.cancel')}
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                deleteModel();
                setShowDeleteConfirmModal(false);
              }}
            >
              {t('common.confirmDelete')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Form {...form}>
        <form
          onSubmit={form.handleSubmit(handleFormSubmit)}
          className="space-y-6"
        >
          <FormField
            control={form.control}
            name="name"
            render={({ field }) => (
              <FormItem>
                <FormLabel>
                  {t('models.modelName')}
                  <span className="text-red-500">*</span>
                </FormLabel>
                <FormControl>
                  <Input {...field} placeholder="gpt-4o" />
                </FormControl>
                <FormDescription>
                  {t('models.modelProviderDescription')}
                </FormDescription>
                <FormMessage />
              </FormItem>
            )}
          />

          <div>
            <FormLabel>{t('models.provider')}</FormLabel>
            <Tabs
              value={providerMode}
              onValueChange={(v) => setProviderMode(v as 'existing' | 'new')}
              className="mt-2"
            >
              <TabsList>
                <TabsTrigger value="existing">
                  {t('models.existingProvider')}
                </TabsTrigger>
                <TabsTrigger value="new">{t('models.newProvider')}</TabsTrigger>
              </TabsList>

              <TabsContent value="existing" className="mt-3">
                <FormField
                  control={form.control}
                  name="provider_uuid"
                  render={({ field }) => (
                    <FormItem>
                      <Select
                        onValueChange={field.onChange}
                        value={field.value}
                      >
                        <SelectTrigger className="bg-background">
                          <SelectValue
                            placeholder={t('models.selectProvider')}
                          />
                        </SelectTrigger>
                        <SelectContent>
                          {providers.map((p) => (
                            <SelectItem key={p.uuid} value={p.uuid}>
                              {p.name} ({p.base_url || 'default'})
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </TabsContent>

              <TabsContent value="new" className="mt-3 space-y-4">
                <FormField
                  control={form.control}
                  name="new_provider_requester"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t('models.requester')}</FormLabel>
                      <Select
                        onValueChange={(v) => {
                          field.onChange(v);
                          const req = requesterList.find((r) => r.value === v);
                          if (req)
                            form.setValue('new_provider_url', req.defaultUrl);
                        }}
                        value={field.value}
                      >
                        <SelectTrigger className="bg-background">
                          <SelectValue
                            placeholder={t('models.selectRequester')}
                          />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectGroup>
                            <SelectLabel>
                              {t('models.modelManufacturer')}
                            </SelectLabel>
                            {requesterList
                              .filter((r) => r.category === 'manufacturer')
                              .map((r) => (
                                <SelectItem key={r.value} value={r.value}>
                                  {r.label}
                                </SelectItem>
                              ))}
                          </SelectGroup>
                          <SelectGroup>
                            <SelectLabel>
                              {t('models.aggregationPlatform')}
                            </SelectLabel>
                            {requesterList
                              .filter((r) => r.category === 'maas')
                              .map((r) => (
                                <SelectItem key={r.value} value={r.value}>
                                  {r.label}
                                </SelectItem>
                              ))}
                          </SelectGroup>
                          <SelectGroup>
                            <SelectLabel>
                              {t('models.selfDeployed')}
                            </SelectLabel>
                            {requesterList
                              .filter((r) => r.category === 'self-hosted')
                              .map((r) => (
                                <SelectItem key={r.value} value={r.value}>
                                  {r.label}
                                </SelectItem>
                              ))}
                          </SelectGroup>
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="new_provider_url"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t('models.requestURL')}</FormLabel>
                      <FormControl>
                        <Input {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="new_provider_api_key"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t('models.apiKey')}</FormLabel>
                      <FormControl>
                        <Input {...field} type="password" />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </TabsContent>
            </Tabs>
          </div>

          <FormField
            control={form.control}
            name="abilities"
            render={() => (
              <FormItem>
                <FormLabel>{t('models.abilities')}</FormLabel>
                <FormDescription>
                  {t('models.selectModelAbilities')}
                </FormDescription>
                {abilityOptions.map((item) => (
                  <FormField
                    key={item.value}
                    control={form.control}
                    name="abilities"
                    render={({ field }) => (
                      <FormItem className="flex flex-row items-start space-x-2 space-y-0">
                        <FormControl>
                          <Checkbox
                            checked={field.value?.includes(item.value)}
                            onCheckedChange={(checked) => {
                              if (checked) {
                                field.onChange([
                                  ...(field.value || []),
                                  item.value,
                                ]);
                              } else {
                                field.onChange(
                                  field.value?.filter(
                                    (v: string) => v !== item.value,
                                  ),
                                );
                              }
                            }}
                          />
                        </FormControl>
                        <FormLabel className="font-normal">
                          {item.label}
                        </FormLabel>
                      </FormItem>
                    )}
                  />
                ))}
              </FormItem>
            )}
          />

          <FormItem>
            <FormLabel>{t('models.extraParameters')}</FormLabel>
            <div className="space-y-2">
              {extraArgs.map((arg, index) => (
                <div key={index} className="flex gap-2">
                  <Input
                    placeholder={t('models.keyName')}
                    value={arg.key}
                    onChange={(e) =>
                      updateExtraArg(index, 'key', e.target.value)
                    }
                  />
                  <Select
                    value={arg.type}
                    onValueChange={(v) => updateExtraArg(index, 'type', v)}
                  >
                    <SelectTrigger className="w-[120px] bg-background">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="string">
                        {t('models.string')}
                      </SelectItem>
                      <SelectItem value="number">
                        {t('models.number')}
                      </SelectItem>
                      <SelectItem value="boolean">
                        {t('models.boolean')}
                      </SelectItem>
                    </SelectContent>
                  </Select>
                  <Input
                    placeholder={t('models.value')}
                    value={arg.value}
                    onChange={(e) =>
                      updateExtraArg(index, 'value', e.target.value)
                    }
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    onClick={() => removeExtraArg(index)}
                  >
                    <span className="text-red-500">×</span>
                  </Button>
                </div>
              ))}
              <Button type="button" variant="outline" onClick={addExtraArg}>
                {t('models.addParameter')}
              </Button>
            </div>
            <FormDescription>
              {t('llm.extraParametersDescription')}
            </FormDescription>
          </FormItem>

          {testErrorMessage && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertTitle>{t('models.testError')}</AlertTitle>
              <AlertDescription className="break-all">
                {testErrorMessage}
              </AlertDescription>
            </Alert>
          )}

          <DialogFooter>
            {editMode && (
              <Button
                type="button"
                variant="destructive"
                onClick={() => setShowDeleteConfirmModal(true)}
              >
                {t('common.delete')}
              </Button>
            )}
            <Button type="submit">
              {editMode ? t('common.save') : t('common.submit')}
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={testModel}
              disabled={modelTesting}
            >
              {t('common.test')}
            </Button>
            <Button type="button" variant="outline" onClick={onFormCancel}>
              {t('common.cancel')}
            </Button>
          </DialogFooter>
        </form>
      </Form>
    </div>
  );
}
