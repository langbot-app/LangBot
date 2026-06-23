import { useState } from 'react';
import type React from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { Bot, Workflow } from 'lucide-react';
import { httpClient } from '@/app/infra/http/HttpClient';
import { AgentKind } from '@/app/infra/entities/api';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import EmojiPicker from '@/components/ui/emoji-picker';

export default function AgentCreateContent({
  onCreated,
}: {
  onCreated: (agentId: string) => void;
}) {
  const { t } = useTranslation();
  const [kind, setKind] = useState<AgentKind>('agent');
  const formSchema = z.object({
    name: z.string().min(1, { message: t('agents.nameRequired') }),
    description: z.string().optional(),
    emoji: z.string().optional(),
  });
  type FormValues = z.infer<typeof formSchema>;
  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: '',
      description: '',
      emoji: '🤖',
    },
  });

  function handleKindChange(nextKind: AgentKind) {
    setKind(nextKind);
    if (!form.getValues('emoji')) {
      form.setValue('emoji', nextKind === 'pipeline' ? '⚙️' : '🤖');
    }
  }

  function handleSubmit(values: FormValues) {
    httpClient
      .createAgent({
        kind,
        name: values.name,
        description: values.description ?? '',
        emoji: values.emoji || (kind === 'pipeline' ? '⚙️' : '🤖'),
      })
      .then((resp) => {
        toast.success(t('agents.createSuccess'));
        onCreated(resp.uuid);
      })
      .catch((err) => {
        toast.error(t('agents.createError') + err.msg);
      });
  }

  const typeOptions: Array<{
    kind: AgentKind;
    icon: React.ElementType;
    title: string;
    description: string;
    badge: string;
  }> = [
    {
      kind: 'agent',
      icon: Bot,
      title: t('agents.agentOrchestration'),
      description: t('agents.agentOrchestrationDescription'),
      badge: t('agents.allEvents'),
    },
    {
      kind: 'pipeline',
      icon: Workflow,
      title: t('agents.pipelineType'),
      description: t('agents.pipelineTypeDescription'),
      badge: t('agents.messageEventsOnly'),
    },
  ];

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between pb-4 shrink-0">
        <h1 className="text-xl font-semibold">{t('agents.create')}</h1>
        <Button type="submit" form="agent-create-form">
          {t('common.submit')}
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto min-h-0">
        <div className="mx-auto max-w-2xl space-y-6">
          <div className="grid gap-3 sm:grid-cols-2">
            {typeOptions.map((option) => {
              const Icon = option.icon;
              const selected = kind === option.kind;
              return (
                <button
                  key={option.kind}
                  type="button"
                  onClick={() => handleKindChange(option.kind)}
                  className={cn(
                    'rounded-lg border bg-card p-4 text-left transition-colors',
                    selected
                      ? 'border-primary ring-2 ring-primary/20'
                      : 'hover:border-primary/60',
                  )}
                >
                  <div className="flex items-start gap-3">
                    <Icon className="mt-0.5 size-5 text-blue-500" />
                    <div className="space-y-1">
                      <div className="font-medium">{option.title}</div>
                      <div className="text-xs text-muted-foreground">
                        {option.badge}
                      </div>
                      <p className="text-sm text-muted-foreground">
                        {option.description}
                      </p>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>

          <Card>
            <CardHeader>
              <CardTitle>{t('agents.basicInfo')}</CardTitle>
              <CardDescription>
                {t('agents.basicInfoDescription')}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Form {...form}>
                <form
                  id="agent-create-form"
                  onSubmit={form.handleSubmit(handleSubmit)}
                  className="space-y-4"
                >
                  <div className="flex gap-4 items-start">
                    <FormField
                      control={form.control}
                      name="name"
                      render={({ field }) => (
                        <FormItem className="flex-1">
                          <FormLabel>
                            {t('common.name')}
                            <span className="text-destructive">*</span>
                          </FormLabel>
                          <FormControl>
                            <Input {...field} value={field.value ?? ''} />
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
                        <FormLabel>{t('common.description')}</FormLabel>
                        <FormControl>
                          <Input {...field} value={field.value ?? ''} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </form>
              </Form>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
