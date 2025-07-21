'use client';

import { useState, useEffect } from 'react';
import { LLMCardVO } from '@/app/home/models/component/llm-card/LLMCardVO';
import styles from './LLMConfig.module.css';
import LLMCard from '@/app/home/models/component/llm-card/LLMCard';
import LLMForm from '@/app/home/models/component/llm-form/LLMForm';
import CreateCardComponent from '@/app/infra/basic-component/create-card-component/CreateCardComponent';
import { httpClient } from '@/app/infra/http/HttpClient';
import { LLMModel } from '@/app/infra/entities/api';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { i18nObj } from '@/i18n/I18nProvider';
import { EmbeddingCardVO } from '@/app/home/models/component/embedding-card/EmbeddingCardVO';
import EmbeddingCard from '@/app/home/models/component/embedding-card/EmbeddingCard';
import EmbeddingForm from '@/app/home/models/component/embedding-form/EmbeddingForm';

export default function LLMConfigPage() {
  const { t } = useTranslation();
  const [cardList, setCardList] = useState<LLMCardVO[]>([]);
  const [modalOpen, setModalOpen] = useState<boolean>(false);
  const [isEditForm, setIsEditForm] = useState(false);
  const [nowSelectedLLM, setNowSelectedLLM] = useState<LLMCardVO | null>(null);
  const [embeddingCardList, setEmbeddingCardList] = useState<EmbeddingCardVO[]>(
    [],
  );
  const [embeddingModalOpen, setEmbeddingModalOpen] = useState<boolean>(false);
  const [isEditEmbeddingForm, setIsEditEmbeddingForm] = useState(false);
  const [nowSelectedEmbedding, setNowSelectedEmbedding] =
    useState<EmbeddingCardVO | null>(null);

  useEffect(() => {
    getLLMModelList();
    getEmbeddingModelList();
  }, []);

  async function getLLMModelList() {
    const requesterNameListResp = await httpClient.getProviderRequesters('llm');
    const requesterNameList = requesterNameListResp.requesters.map((item) => {
      return {
        label: i18nObj(item.label),
        value: item.name,
      };
    });

    httpClient
      .getProviderLLMModels()
      .then((resp) => {
        const llmModelList: LLMCardVO[] = resp.models.map((model: LLMModel) => {
          console.log('model', model);
          return new LLMCardVO({
            id: model.uuid,
            iconURL: httpClient.getProviderRequesterIconURL(model.requester),
            name: model.name,
            providerLabel:
              requesterNameList.find((item) => item.value === model.requester)
                ?.label || model.requester.substring(0, 10),
            baseURL: model.requester_config?.base_url,
            abilities: model.abilities || [],
          });
        });
        console.log('get llmModelList', llmModelList);
        setCardList(llmModelList);
      })
      .catch((err) => {
        console.error('get LLM model list error', err);
        toast.error(t('models.getModelListError') + err.message);
      });
  }

  function selectLLM(cardVO: LLMCardVO) {
    setIsEditForm(true);
    setNowSelectedLLM(cardVO);
    console.log('set now vo', cardVO);
    setModalOpen(true);
  }
  function handleCreateModelClick() {
    setIsEditForm(false);
    setNowSelectedLLM(null);
    setModalOpen(true);
  }
  function selectEmbedding(cardVO: EmbeddingCardVO) {
    setIsEditEmbeddingForm(true);
    setNowSelectedEmbedding(cardVO);
    setEmbeddingModalOpen(true);
  }

  function handleCreateEmbeddingModelClick() {
    setIsEditEmbeddingForm(false);
    setNowSelectedEmbedding(null);
    setEmbeddingModalOpen(true);
  }
  async function getEmbeddingModelList() {
    const requesterNameListResp =
      await httpClient.getProviderRequesters('text-embedding');
    const requesterNameList = requesterNameListResp.requesters.map((item) => {
      return {
        label: i18nObj(item.label),
        value: item.name,
      };
    });

    httpClient
      .getProviderEmbeddingModels()
      .then((resp) => {
        const embeddingModelList: EmbeddingCardVO[] = resp.models.map(
          (model: {
            uuid: string;
            requester: string;
            name: string;
            requester_config?: { base_url?: string };
          }) => {
            return new EmbeddingCardVO({
              id: model.uuid,
              iconURL: httpClient.getProviderRequesterIconURL(model.requester),
              name: model.name,
              providerLabel:
                requesterNameList.find((item) => item.value === model.requester)
                  ?.label || model.requester.substring(0, 10),
              baseURL: model.requester_config?.base_url || '',
            });
          },
        );
        setEmbeddingCardList(embeddingModelList);
      })
      .catch((err) => {
        console.error('get Embedding model list error', err);
        toast.error(t('embedding.getModelListError') + err.message);
      });
  }

  return (
    <div>
      <Dialog open={modalOpen} onOpenChange={setModalOpen}>
        <DialogContent className="w-[700px] p-6">
          <DialogHeader>
            <DialogTitle>
              {isEditForm ? t('models.editModel') : t('models.createModel')}
            </DialogTitle>
          </DialogHeader>
          <LLMForm
            editMode={isEditForm}
            initLLMId={nowSelectedLLM?.id}
            onFormSubmit={() => {
              setModalOpen(false);
              getLLMModelList();
            }}
            onFormCancel={() => {
              setModalOpen(false);
            }}
            onLLMDeleted={() => {
              setModalOpen(false);
              getLLMModelList();
            }}
          />
        </DialogContent>
      </Dialog>
      <Dialog open={embeddingModalOpen} onOpenChange={setEmbeddingModalOpen}>
        <DialogContent className="w-[700px] p-6">
          <DialogHeader>
            <DialogTitle>
              {isEditEmbeddingForm
                ? t('embedding.editModel')
                : t('embedding.createModel')}
            </DialogTitle>
          </DialogHeader>
          <EmbeddingForm
            editMode={isEditEmbeddingForm}
            initEmbeddingId={nowSelectedEmbedding?.id}
            onFormSubmit={() => {
              setEmbeddingModalOpen(false);
              getEmbeddingModelList();
            }}
            onFormCancel={() => {
              setEmbeddingModalOpen(false);
            }}
            onEmbeddingDeleted={() => {
              setEmbeddingModalOpen(false);
              getEmbeddingModelList();
            }}
          />
        </DialogContent>
      </Dialog>

      <Tabs defaultValue="llm" className="w-full">
        <div className="flex flex-row gap-0 mb-4">
          <div className="flex flex-row justify-between items-center px-[0.8rem]">
            <TabsList className="shadow-md py-5 bg-[#f0f0f0]">
              <TabsTrigger value="llm" className="px-6 py-4 cursor-pointer">
                {t('llm.llmModels')}
              </TabsTrigger>
              <TabsTrigger
                value="embedding"
                className="px-6 py-4 cursor-pointer"
              >
                {t('embedding.embeddingModels')}
              </TabsTrigger>
            </TabsList>
          </div>
          <TabsContent value="llm">
            <div className="flex flex-row justify-between items-center px-[0.4rem] h-full">
              <p className="text-sm text-gray-500">{t('llm.description')}</p>
            </div>
          </TabsContent>
          <TabsContent value="embedding">
            <div className="flex flex-row justify-between items-center px-[0.4rem] h-full">
              <p className="text-sm text-gray-500">
                {t('embedding.description')}
              </p>
            </div>
          </TabsContent>
        </div>

        <TabsContent value="llm">
          <div className={`${styles.modelListContainer}`}>
            <CreateCardComponent
              width={'100%'}
              height={'10rem'}
              plusSize={'90px'}
              onClick={handleCreateModelClick}
            />
            {cardList.map((cardVO) => {
              return (
                <div
                  key={cardVO.id}
                  onClick={() => {
                    selectLLM(cardVO);
                  }}
                >
                  <LLMCard cardVO={cardVO}></LLMCard>
                </div>
              );
            })}
          </div>
        </TabsContent>

        <TabsContent value="embedding">
          <div className={`${styles.modelListContainer}`}>
            <CreateCardComponent
              width={'100%'}
              height={'10rem'}
              plusSize={'90px'}
              onClick={handleCreateEmbeddingModelClick}
            />
            {embeddingCardList.map((cardVO) => {
              return (
                <div
                  key={cardVO.id}
                  onClick={() => {
                    selectEmbedding(cardVO);
                  }}
                >
                  <EmbeddingCard cardVO={cardVO}></EmbeddingCard>
                </div>
              );
            })}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
