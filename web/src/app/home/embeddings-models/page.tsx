'use client';

import { useState, useEffect } from 'react';
import { EmbeddingsCardVO } from '@/app/home/embeddings-models/component/embeddings-card/EmbeddingsCardVO';
import styles from './EmbeddingsConfig.module.css';
import EmbeddingsCard from '@/app/home/embeddings-models/component/embeddings-card/EmbeddingsCard';
import EmbeddingsForm from '@/app/home/embeddings-models/component/embeddings-form/EmbeddingsForm';
import CreateCardComponent from '@/app/infra/basic-component/create-card-component/CreateCardComponent';
import { httpClient } from '@/app/infra/http/HttpClient';
import { EmbeddingsModel } from '@/app/infra/entities/api';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { i18nObj } from '@/i18n/I18nProvider';

export default function EmbeddingsConfigPage() {
  const { t } = useTranslation();
  const [cardList, setCardList] = useState<EmbeddingsCardVO[]>([]);
  const [modalOpen, setModalOpen] = useState<boolean>(false);
  const [isEditForm, setIsEditForm] = useState(false);
  const [nowSelectedEmbeddings, setNowSelectedEmbeddings] =
    useState<EmbeddingsCardVO | null>(null);

  useEffect(() => {
    getEmbeddingsModelList();
  }, []);

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
          (model: EmbeddingsModel) => {
            return new EmbeddingsCardVO({
              id: model.uuid,
              iconURL: httpClient.getProviderRequesterIconURL(model.requester),
              name: model.name,
              providerLabel:
                requesterNameList.find((item) => item.value === model.requester)
                  ?.label || model.requester.substring(0, 10),
              baseURL: model.requester_config?.base_url,
              dimensions: model.dimensions,
              encoding_format: model.encoding_format,
            });
          },
        );
        setCardList(embeddingsModelList);
      })
      .catch((err) => {
        console.error('get Embeddings model list error', err);
        toast.error(t('embeddings.getModelListError') + err.message);
      });
  }

  function selectEmbeddings(cardVO: EmbeddingsCardVO) {
    setIsEditForm(true);
    setNowSelectedEmbeddings(cardVO);
    setModalOpen(true);
  }

  function handleCreateModelClick() {
    setIsEditForm(false);
    setNowSelectedEmbeddings(null);
    setModalOpen(true);
  }

  return (
    <div>
      <Dialog open={modalOpen} onOpenChange={setModalOpen}>
        <DialogContent className="w-[700px] p-6">
          <DialogHeader>
            <DialogTitle>
              {isEditForm
                ? t('embeddings.editModel')
                : t('embeddings.createModel')}
            </DialogTitle>
          </DialogHeader>
          <EmbeddingsForm
            editMode={isEditForm}
            initEmbeddingsId={nowSelectedEmbeddings?.id}
            onFormSubmit={() => {
              setModalOpen(false);
              getEmbeddingsModelList();
            }}
            onFormCancel={() => {
              setModalOpen(false);
            }}
            onEmbeddingsDeleted={() => {
              setModalOpen(false);
              getEmbeddingsModelList();
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
                selectEmbeddings(cardVO);
              }}
            >
              <EmbeddingsCard cardVO={cardVO}></EmbeddingsCard>
            </div>
          );
        })}
      </div>
    </div>
  );
}
