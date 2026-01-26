import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useTranslation } from 'react-i18next';
import { Input } from '@/components/ui/input';
import EmojiPicker from '@/components/ui/emoji-picker';
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
  FormDescription,
} from '@/components/ui/form';
import { httpClient, systemInfo } from '@/app/infra/http/HttpClient';
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { KnowledgeBase, EmbeddingModel } from '@/app/infra/entities/api';
import { toast } from 'sonner';

const getFormSchema = (t: (key: string) => string) =>
  z.object({
    name: z.string().min(1, { message: t('knowledge.kbNameRequired') }),
    description: z
      .string()
      .min(1, { message: t('knowledge.kbDescriptionRequired') }),
    emoji: z.string().optional(),
    embeddingModelUUID: z
      .string()
      .min(1, { message: t('knowledge.embeddingModelUUIDRequired') }),
    top_k: z
      .number()
      .min(1, { message: t('knowledge.topKRequired') })
      .max(30, { message: t('knowledge.topKMax') }),
  });

export default function KBForm({
  initKbId,
  onNewKbCreated,
  onKbUpdated,
}: {
  initKbId?: string;
  onNewKbCreated: (kbId: string) => void;
  onKbUpdated: (kbId: string) => void;
}) {
  const { t } = useTranslation();
  const formSchema = getFormSchema(t);

  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: '',
      description: t('knowledge.defaultDescription'),
      emoji: '📚',
      embeddingModelUUID: '',
      top_k: 5,
    },
  });

  const [embeddingModels, setEmbeddingModels] = useState<EmbeddingModel[]>([]);

  useEffect(() => {
    getEmbeddingModelNameList().then(() => {
      if (initKbId) {
        getKbConfig(initKbId).then((val) => {
          form.setValue('name', val.name);
          form.setValue('description', val.description);
          form.setValue('emoji', val.emoji);
          form.setValue('embeddingModelUUID', val.embeddingModelUUID);
          form.setValue('top_k', val.top_k || 5);
        });
      }
    });
  }, []);

  const getKbConfig = async (
    kbId: string,
  ): Promise<z.infer<typeof formSchema>> => {
    return new Promise((resolve) => {
      httpClient.getKnowledgeBase(kbId).then((res) => {
        resolve({
          name: res.base.name,
          description: res.base.description,
          emoji: res.base.emoji || '📚',
          embeddingModelUUID: res.base.embedding_model_uuid,
          top_k: res.base.top_k || 5,
        });
      });
    });
  };

  const getEmbeddingModelNameList = async () => {
    const resp = await httpClient.getProviderEmbeddingModels();
    let models = resp.models;
    // Filter out space-chat-completions models when models service is disabled
    if (systemInfo.disable_models_service) {
      models = models.filter(
        (m) => m.provider?.requester !== 'space-chat-completions',
      );
    }
    setEmbeddingModels(models);
  };

  const onSubmit = (data: z.infer<typeof formSchema>) => {
    if (initKbId) {
      // update knowledge base
      const updateKb: KnowledgeBase = {
        name: data.name,
        description: data.description,
        emoji: data.emoji,
        embedding_model_uuid: data.embeddingModelUUID,
        top_k: data.top_k,
      };
      httpClient
        .updateKnowledgeBase(initKbId, updateKb)
        .then((res) => {
          onKbUpdated(res.uuid);
          toast.success(t('knowledge.updateKnowledgeBaseSuccess'));
        })
        .catch((err) => {
          console.error('update knowledge base failed', err);
          toast.error(t('knowledge.updateKnowledgeBaseFailed'));
        });
    } else {
      // create knowledge base
      const newKb: KnowledgeBase = {
        name: data.name,
        description: data.description,
        emoji: data.emoji,
        embedding_model_uuid: data.embeddingModelUUID,
        top_k: data.top_k,
      };
      httpClient
        .createKnowledgeBase(newKb)
        .then((res) => {
          onNewKbCreated(res.uuid);
        })
        .catch((err) => {
          console.error('create knowledge base failed', err);
        });
    }
  };

  return (
    <>
      <Form {...form}>
        <form
          onSubmit={form.handleSubmit(onSubmit)}
          id="kb-form"
          className="space-y-8"
        >
          <div className="space-y-4">
            {/* Name and Emoji in same row */}
            <div className="flex gap-4 items-start">
              <FormField
                control={form.control}
                name="name"
                render={({ field }) => (
                  <FormItem className="flex-1">
                    <FormLabel>
                      {t('knowledge.kbName')}
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
                name="emoji"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t('common.icon')}</FormLabel>
                    <FormControl>
                      <EmojiPicker
                        value={field.value}
                        onChange={field.onChange}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
            <FormField
              control={form.control}
              name="description"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>
                    {t('knowledge.kbDescription')}
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
              name="embeddingModelUUID"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>
                    {t('knowledge.embeddingModelUUID')}
                    <span className="text-red-500">*</span>
                  </FormLabel>
                  <FormControl>
                    <div className="relative">
                      <Select
                        disabled={!!initKbId}
                        onValueChange={(value) => {
                          field.onChange(value);
                        }}
                        value={field.value}
                      >
                        <SelectTrigger className="w-[180px] bg-[#ffffff] dark:bg-[#2a2a2e]">
                          <SelectValue
                            placeholder={t('knowledge.selectEmbeddingModel')}
                          />
                        </SelectTrigger>
                        <SelectContent className="fixed z-[1000]">
                          {(() => {
                            const grouped = embeddingModels.reduce(
                              (acc, model) => {
                                const providerName =
                                  model.provider?.name ||
                                  model.provider?.requester ||
                                  'Unknown';
                                if (!acc[providerName]) acc[providerName] = [];
                                acc[providerName].push(model);
                                return acc;
                              },
                              {} as Record<string, EmbeddingModel[]>,
                            );
                            return Object.entries(grouped).map(
                              ([providerName, models]) => (
                                <SelectGroup key={providerName}>
                                  <SelectLabel>{providerName}</SelectLabel>
                                  {models.map((model) => (
                                    <SelectItem
                                      key={model.uuid}
                                      value={model.uuid}
                                    >
                                      {model.name}
                                    </SelectItem>
                                  ))}
                                </SelectGroup>
                              ),
                            );
                          })()}
                        </SelectContent>
                      </Select>
                    </div>
                  </FormControl>
                  <FormDescription>
                    {initKbId
                      ? t('knowledge.cannotChangeEmbeddingModel')
                      : t('knowledge.embeddingModelDescription')}
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="top_k"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>
                    {t('knowledge.topK')}
                    <span className="text-red-500">*</span>
                  </FormLabel>
                  <FormControl>
                    <Input
                      type="number"
                      {...field}
                      onChange={(e) => field.onChange(Number(e.target.value))}
                      className="w-[180px] h-10 text-base appearance-none"
                    />
                  </FormControl>
                  <FormDescription>
                    {t('knowledge.topKdescription')}
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
          </div>
        </form>
      </Form>
    </>
  );
}
