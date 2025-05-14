'use client';
import { useState, useEffect } from 'react';
import CreateCardComponent from '@/app/infra/basic-component/create-card-component/CreateCardComponent';
import PipelineFormComponent from './components/pipeline-form/PipelineFormComponent';
import { httpClient } from '@/app/infra/http/HttpClient';
import { PipelineCardVO } from '@/app/home/pipelines/components/pipeline-card/PipelineCardVO';
import PipelineCard from '@/app/home/pipelines/components/pipeline-card/PipelineCard';
import { PipelineFormEntity } from '@/app/infra/entities/pipeline';
import styles from './pipelineConfig.module.css';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
export default function PluginConfigPage() {
  const { t } = useTranslation();
  const [modalOpen, setModalOpen] = useState<boolean>(false);
  const [isEditForm, setIsEditForm] = useState(false);
  const [pipelineList, setPipelineList] = useState<PipelineCardVO[]>([]);
  const [selectedPipelineId, setSelectedPipelineId] = useState('');
  const [selectedPipelineFormValue, setSelectedPipelineFormValue] =
    useState<PipelineFormEntity>({
      basic: {},
      ai: {},
      trigger: {},
      safety: {},
      output: {},
    });
  const [disableForm, setDisableForm] = useState(false);
  const [selectedPipelineIsDefault, setSelectedPipelineIsDefault] =
    useState(false);

  useEffect(() => {
    getPipelines();
  }, []);

  function getPipelines() {
    httpClient
      .getPipelines()
      .then((value) => {
        const currentTime = new Date();
        const pipelineList = value.pipelines.map((pipeline) => {
          const lastUpdatedTimeAgo = Math.floor(
            (currentTime.getTime() -
              new Date(
                pipeline.updated_at ?? currentTime.getTime(),
              ).getTime()) /
              1000 /
              60 /
              60 /
              24,
          );

          const lastUpdatedTimeAgoText =
            lastUpdatedTimeAgo > 0
              ? ` ${lastUpdatedTimeAgo} ${t('pipelines.daysAgo')}`
              : t('pipelines.today');

          return new PipelineCardVO({
            lastUpdatedTimeAgo: lastUpdatedTimeAgoText,
            description: pipeline.description,
            id: pipeline.uuid ?? '',
            name: pipeline.name,
            isDefault: pipeline.is_default ?? false,
          });
        });
        setPipelineList(pipelineList);
      })
      .catch((error) => {
        console.log(error);
        toast.error(t('pipelines.getPipelineListError') + error.message);
      });
  }

  function getSelectedPipelineForm(id?: string) {
    httpClient.getPipeline(id ?? selectedPipelineId).then((value) => {
      setSelectedPipelineFormValue({
        ai: value.pipeline.config.ai,
        basic: {
          description: value.pipeline.description,
          name: value.pipeline.name,
        },
        output: value.pipeline.config.output,
        safety: value.pipeline.config.safety,
        trigger: value.pipeline.config.trigger,
      });
      setSelectedPipelineIsDefault(value.pipeline.is_default ?? false);
      setDisableForm(false);
    });
  }

  return (
    <div className={styles.configPageContainer}>
      <Dialog open={modalOpen} onOpenChange={setModalOpen}>
        <DialogContent className="w-[700px] max-h-[80vh] p-0 flex flex-col">
          <DialogHeader className="px-6 pt-6 pb-4">
            <DialogTitle>
              {isEditForm
                ? t('pipelines.editPipeline')
                : t('pipelines.createPipeline')}
            </DialogTitle>
          </DialogHeader>
          <div className="flex-1 overflow-y-auto px-6">
            <PipelineFormComponent
              onNewPipelineCreated={(pipelineId) => {
                setDisableForm(true);
                setIsEditForm(true);
                setModalOpen(true);
                setSelectedPipelineId(pipelineId);
                getSelectedPipelineForm(pipelineId);
              }}
              onFinish={() => {
                getPipelines();
                setModalOpen(false);
              }}
              isEditMode={isEditForm}
              pipelineId={selectedPipelineId}
              disableForm={disableForm}
              initValues={selectedPipelineFormValue}
              isDefaultPipeline={selectedPipelineIsDefault}
            />
          </div>
        </DialogContent>
      </Dialog>

      <div className={styles.pipelineListContainer}>
        <CreateCardComponent
          width={'100%'}
          height={'10rem'}
          plusSize={'90px'}
          onClick={() => {
            setIsEditForm(false);
            setModalOpen(true);
          }}
        />

        {pipelineList.map((pipeline) => {
          return (
            <div
              key={pipeline.id}
              onClick={() => {
                setDisableForm(true);
                setIsEditForm(true);
                setModalOpen(true);
                setSelectedPipelineId(pipeline.id);
                getSelectedPipelineForm(pipeline.id);
              }}
            >
              <PipelineCard cardVO={pipeline} />
            </div>
          );
        })}
      </div>
    </div>
  );
}
