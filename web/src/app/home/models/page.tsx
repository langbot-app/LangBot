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
import { EmbeddingsCardVO } from '@/app/home/embeddings-models/component/embeddings-card/EmbeddingsCardVO';
import EmbeddingsCard from '@/app/home/embeddings-models/component/embeddings-card/EmbeddingsCard';
import EmbeddingsForm from '@/app/home/embeddings-models/component/embeddings-form/EmbeddingsForm';

export default function LLMConfigPage() {
  const { t } = useTranslation();
  const [cardList, setCardList] = useState<LLMCardVO[]>([]);
  const [modalOpen, setModalOpen] = useState<boolean>(false);
  const [isEditForm, setIsEditForm] = useState(false);
  const [nowSelectedLLM, setNowSelectedLLM] = useState<LLMCardVO | null>(null);
  const [embeddingsCardList, setEmbeddingsCardList] = useState<
    EmbeddingsCardVO[]
  >([]);
  const [embeddingsModalOpen, setEmbeddingsModalOpen] =
    useState<boolean>(false);
  const [isEditEmbeddingsForm, setIsEditEmbeddingsForm] = useState(false);
  const [nowSelectedEmbeddings, setNowSelectedEmbeddings] =
    useState<EmbeddingsCardVO | null>(null);

  useEffect(() => {
    getLLMModelList();
    getEmbeddingsModelList();
  }, []);

  async function getLLMModelList() {
    const requesterNameListResp = await httpClient.getProviderRequesters();
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
  function selectEmbeddings(cardVO: EmbeddingsCardVO) {
    setIsEditEmbeddingsForm(true);
    setNowSelectedEmbeddings(cardVO);
    setEmbeddingsModalOpen(true);
  }

  function handleCreateEmbeddingsModelClick() {
    setIsEditEmbeddingsForm(false);
    setNowSelectedEmbeddings(null);
    setEmbeddingsModalOpen(true);
  }
  async function getEmbeddingsModelList() {
    const requesterNameListResp = await httpClient.getProviderRequesters();
    const requesterNameList = requesterNameListResp.requesters.map((item) => {
      return {
        label: i18nObj(item.label),
        value: item.name,
      };
    });

    httpClient
      .getProviderEmbeddingsModels()
      .then((resp) => {
        const embeddingsModelList: EmbeddingsCardVO[] = resp.models.map(
          (model: {
            uuid: string;
            requester: string;
            name: string;
            requester_config?: { base_url?: string };
            dimensions?: number;
            encoding_format?: string;
          }) => {
            return new EmbeddingsCardVO({
              id: model.uuid,
              iconURL: httpClient.getProviderRequesterIconURL(model.requester),
              name: model.name,
              providerLabel:
                requesterNameList.find((item) => item.value === model.requester)
                  ?.label || model.requester.substring(0, 10),
              baseURL: model.requester_config?.base_url || '',
              dimensions: model.dimensions,
              encoding_format: model.encoding_format,
            });
          },
        );
        setEmbeddingsCardList(embeddingsModelList);
      })
      .catch((err) => {
        console.error('get Embeddings model list error', err);
        toast.error(t('embeddings.getModelListError') + err.message);
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
      <Dialog open={embeddingsModalOpen} onOpenChange={setEmbeddingsModalOpen}>
        <DialogContent className="w-[700px] p-6">
          <DialogHeader>
            <DialogTitle>
              {isEditEmbeddingsForm
                ? t('embeddings.editModel')
                : t('embeddings.createModel')}
            </DialogTitle>
          </DialogHeader>
          <EmbeddingsForm
            editMode={isEditEmbeddingsForm}
            initEmbeddingsId={nowSelectedEmbeddings?.id}
            onFormSubmit={() => {
              setEmbeddingsModalOpen(false);
              getEmbeddingsModelList();
            }}
            onFormCancel={() => {
              setEmbeddingsModalOpen(false);
            }}
            onEmbeddingsDeleted={() => {
              setEmbeddingsModalOpen(false);
              getEmbeddingsModelList();
            }}
          />
        </DialogContent>
      </Dialog>
      <Tabs defaultValue="llm" className="w-full">
        <div className="flex flex-row justify-between items-center px-[0.8rem]">
          <TabsList className="shadow-md py-5 bg-[#f0f0f0]">
            <TabsTrigger value="llm" className="px-6 py-4 cursor-pointer">
              {t('models.llmModels')}
            </TabsTrigger>
            <TabsTrigger
              value="embeddings"
              className="px-6 py-4 cursor-pointer"
            >
              {t('embeddings.embeddingsModels')}
            </TabsTrigger>
          </TabsList>
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

        <TabsContent value="embeddings">
          <div className={`${styles.modelListContainer}`}>
            <CreateCardComponent
              width={'100%'}
              height={'10rem'}
              plusSize={'90px'}
              onClick={handleCreateEmbeddingsModelClick}
            />
            {embeddingsCardList.map((cardVO) => {
              return (
                <div
                  key={cardVO.id}
                  onClick={() => {
                    selectEmbeddings(cardVO);
                  }}
                >
                  <EmbeddingsCard cardVO={cardVO}></EmbeddingsCard>
                </div>
              );
            })}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
