import { useEffect, useState } from 'react';
import { httpClient } from '@/app/infra/http/HttpClient';

import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { useTranslation } from 'react-i18next';

import { Button } from '@/components/ui/button';
import {
  Form,
  FormControl,
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
import { DialogFooter } from '@/components/ui/dialog';
import { toast } from 'sonner';
import { extractI18nObject } from '@/i18n/I18nProvider';

const getFormSchema = (t: (key: string) => string) =>
  z.object({
    name: z.string().min(1, { message: t('models.providerNameRequired') }),
    requester: z.string().min(1, { message: t('models.requesterRequired') }),
    base_url: z.string(),
    api_key: z.string().optional(),
  });

interface ProviderFormProps {
  providerId?: string;
  onFormSubmit: () => void;
  onFormCancel: () => void;
}

export default function ProviderForm({
  providerId,
  onFormSubmit,
  onFormCancel,
}: ProviderFormProps) {
  const { t } = useTranslation();
  const formSchema = getFormSchema(t);

  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: '',
      requester: '',
      base_url: '',
      api_key: '',
    },
  });

  const [requesterList, setRequesterList] = useState<
    { label: string; value: string; category: string; defaultUrl: string }[]
  >([]);

  useEffect(() => {
    loadRequesters();
    if (providerId) {
      loadProvider(providerId);
    }
  }, [providerId]);

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

  async function loadProvider(id: string) {
    const resp = await httpClient.getModelProvider(id);
    const provider = resp.provider;

    form.setValue('name', provider.name);
    form.setValue('requester', provider.requester);
    form.setValue('base_url', provider.base_url);
    form.setValue('api_key', provider.api_keys?.[0] || '');
  }

  async function handleFormSubmit(values: z.infer<typeof formSchema>) {
    const data = {
      name: values.name,
      requester: values.requester,
      base_url: values.base_url,
      api_keys: values.api_key ? [values.api_key] : [],
    };

    try {
      if (providerId) {
        await httpClient.updateModelProvider(providerId, data);
        toast.success(t('models.providerSaved'));
      } else {
        await httpClient.createModelProvider(data);
        toast.success(t('models.providerCreated'));
      }
      onFormSubmit();
    } catch (err) {
      toast.error(t('models.providerSaveError') + (err as Error).message);
    }
  }

  return (
    <Form {...form}>
      <form
        onSubmit={form.handleSubmit(handleFormSubmit)}
        className="space-y-4"
      >
        <FormField
          control={form.control}
          name="name"
          render={({ field }) => (
            <FormItem>
              <FormLabel>
                {t('models.providerName')}
                <span className="text-red-500">*</span>
              </FormLabel>
              <FormControl>
                <Input {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="requester"
          render={({ field }) => (
            <FormItem>
              <FormLabel>
                {t('models.requester')}
                <span className="text-red-500">*</span>
              </FormLabel>
              <Select
                onValueChange={(v) => {
                  field.onChange(v);
                  const req = requesterList.find((r) => r.value === v);
                  if (req && !form.getValues('base_url')) {
                    form.setValue('base_url', req.defaultUrl);
                  }
                }}
                value={field.value}
              >
                <SelectTrigger className="bg-background">
                  <SelectValue placeholder={t('models.selectRequester')} />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectLabel>{t('models.modelManufacturer')}</SelectLabel>
                    {requesterList
                      .filter((r) => r.category === 'manufacturer')
                      .map((r) => (
                        <SelectItem key={r.value} value={r.value}>
                          {r.label}
                        </SelectItem>
                      ))}
                  </SelectGroup>
                  <SelectGroup>
                    <SelectLabel>{t('models.aggregationPlatform')}</SelectLabel>
                    {requesterList
                      .filter((r) => r.category === 'maas')
                      .map((r) => (
                        <SelectItem key={r.value} value={r.value}>
                          {r.label}
                        </SelectItem>
                      ))}
                  </SelectGroup>
                  <SelectGroup>
                    <SelectLabel>{t('models.selfDeployed')}</SelectLabel>
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
          name="base_url"
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
          name="api_key"
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

        <DialogFooter>
          <Button type="submit">{t('common.save')}</Button>
          <Button type="button" variant="outline" onClick={onFormCancel}>
            {t('common.cancel')}
          </Button>
        </DialogFooter>
      </form>
    </Form>
  );
}
