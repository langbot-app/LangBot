'use client';

import { useState, useEffect } from 'react';
import { LLMCardVO } from '@/app/home/models/component/llm-card/LLMCardVO';
import styles from './LLMConfig.module.css';
import LLMCard from '@/app/home/models/component/llm-card/LLMCard';
import LLMForm from '@/app/home/models/component/llm-form/LLMForm';
import CreateCardComponent from '@/app/infra/basic-component/create-card-component/CreateCardComponent';
import { httpClient } from '@/app/infra/http/HttpClient';
import { LLMModel } from '@/app/infra/entities/api';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { i18nObj } from '@/i18n/I18nProvider';

export default function LLMConfigPage() {
  const { t } = useTranslation();
  const [cardList, setCardList] = useState<LLMCardVO[]>([]);
  const [modalOpen, setModalOpen] = useState<boolean>(false);
  const [isEditForm, setIsEditForm] = useState(false);
  const [nowSelectedLLM, setNowSelectedLLM] = useState<LLMCardVO | null>(null);

  useEffect(() => {
    getLLMModelList();
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
    </div>
  );
}
