import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useTranslation } from 'react-i18next';
import { Input } from '@/components/ui/input';
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
  FormDescription,
} from '@/components/ui/form';
import { IEmbeddingModelEntity } from './ChooseEntity';
import { httpClient } from '@/app/infra/http/HttpClient';
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { KnowledgeBase } from '@/app/infra/entities/api';
import { toast } from 'sonner';

const getFormSchema = (t: (key: string) => string) =>
  z.object({
    name: z.string().min(1, { message: t('knowledge.kbNameRequired') }),
    description: z
      .string()
      .min(1, { message: t('knowledge.kbDescriptionRequired') }),
    embeddingModelUUID: z
      .string()
      .min(1, { message: t('knowledge.embeddingModelUUIDRequired') }),
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
      embeddingModelUUID: '',
    },
  });

  const [embeddingModelNameList, setEmbeddingModelNameList] = useState<
    IEmbeddingModelEntity[]
  >([]);

  useEffect(() => {
    getEmbeddingModelNameList().then(() => {
      if (initKbId) {
        getKbConfig(initKbId).then((val) => {
          form.setValue('name', val.name);
          form.setValue('description', val.description);
          form.setValue('embeddingModelUUID', val.embeddingModelUUID);
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
          embeddingModelUUID: res.base.embedding_model_uuid,
        });
      });
    });
  };

  const getEmbeddingModelNameList = async () => {
    const resp = await httpClient.getProviderEmbeddingModels();
    setEmbeddingModelNameList(
      resp.models.map((item) => {
        return {
          label: item.name,
          value: item.uuid,
        };
      }),
    );
  };

  const onSubmit = (data: z.infer<typeof formSchema>) => {
    console.log('data', data);

    if (initKbId) {
      // update knowledge base
      const updateKb: KnowledgeBase = {
        name: data.name,
        description: data.description,
        embedding_model_uuid: data.embeddingModelUUID,
      };
      httpClient
        .updateKnowledgeBase(initKbId, updateKb)
        .then((res) => {
          console.log('update knowledge base success', res);
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
        embedding_model_uuid: data.embeddingModelUUID,
      };
      httpClient
        .createKnowledgeBase(newKb)
        .then((res) => {
          console.log('create knowledge base success', res);
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
            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
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
                          console.log('value', value);
                        }}
                        value={field.value}
                      >
                        <SelectTrigger className="w-[180px]">
                          <SelectValue
                            placeholder={t('knowledge.selectEmbeddingModel')}
                          />
                        </SelectTrigger>
                        <SelectContent className="fixed z-[1000]">
                          <SelectGroup>
                            {embeddingModelNameList.map((item) => (
                              <SelectItem key={item.value} value={item.value}>
                                {item.label}
                              </SelectItem>
                            ))}
                          </SelectGroup>
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
          </div>
        </form>
      </Form>
    </>
  );
}
