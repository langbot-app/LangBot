'use client';
import { useState, useEffect } from 'react';
import CreateCardComponent from '@/app/infra/basic-component/create-card-component/CreateCardComponent';
import { httpClient } from '@/app/infra/http/HttpClient';
import { PipelineCardVO } from '@/app/home/pipelines/components/pipeline-card/PipelineCardVO';
import PipelineCard from '@/app/home/pipelines/components/pipeline-card/PipelineCard';
import styles from './pipelineConfig.module.css';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import PipelineDialog from './PipelineDetailDialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

export default function PluginConfigPage() {
  const { t } = useTranslation();
  const [dialogOpen, setDialogOpen] = useState<boolean>(false);
  const [isEditForm, setIsEditForm] = useState(false);
  const [pipelineList, setPipelineList] = useState<PipelineCardVO[]>([]);
  const [selectedPipelineId, setSelectedPipelineId] = useState('');

  const [selectedPipelineIsDefault, setSelectedPipelineIsDefault] =
    useState(false);
  const [sortByValue, setSortByValue] = useState<string>('created_at');
  const [sortOrderValue, setSortOrderValue] = useState<string>('DESC');

  useEffect(() => {
    getPipelines();
  }, []);

  function getPipelines(
    sortBy: string = sortByValue,
    sortOrder: string = sortOrderValue,
  ) {
    httpClient
      .getPipelines(sortBy, sortOrder)
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

  const handlePipelineClick = (pipelineId: string) => {
    setSelectedPipelineId(pipelineId);
    setIsEditForm(true);
    setDialogOpen(true);
  };

  const handleCreateNew = () => {
    setIsEditForm(false);
    setSelectedPipelineId('');

    setSelectedPipelineIsDefault(false);
    setDialogOpen(true);
  };

  function handleSortChange(value: string) {
    const [newSortBy, newSortOrder] = value.split(',').map((s) => s.trim());
    setSortByValue(newSortBy);
    setSortOrderValue(newSortOrder);
    getPipelines(newSortBy, newSortOrder);
  }

  return (
    <div className={styles.configPageContainer}>
      <PipelineDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        pipelineId={selectedPipelineId || undefined}
        isEditMode={isEditForm}
        isDefaultPipeline={selectedPipelineIsDefault}
        onFinish={() => {
          getPipelines();
        }}
        onNewPipelineCreated={(pipelineId) => {
          getPipelines();
          setSelectedPipelineId(pipelineId);
          setIsEditForm(true);
          setDialogOpen(true);
        }}
        onDeletePipeline={() => {
          getPipelines();
          setDialogOpen(false);
        }}
        onCancel={() => {
          setDialogOpen(false);
        }}
      />

      <div className="flex flex-row justify-between items-center mb-4 px-[0.8rem]">
        <Select
          value={`${sortByValue},${sortOrderValue}`}
          onValueChange={handleSortChange}
        >
          <SelectTrigger className="w-[180px] cursor-pointer bg-white dark:bg-gray-800">
            <SelectValue placeholder={t('pipelines.sortBy')} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="created_at,DESC">
              {t('pipelines.newestCreated')}
            </SelectItem>
            <SelectItem value="updated_at,DESC">
              {t('pipelines.recentlyEdited')}
            </SelectItem>
            <SelectItem value="updated_at,ASC">
              {t('pipelines.earliestEdited')}
            </SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div className={styles.pipelineListContainer}>
        <CreateCardComponent
          width={'100%'}
          height={'10rem'}
          plusSize={'90px'}
          onClick={handleCreateNew}
        />

        {pipelineList.map((pipeline) => {
          return (
            <div
              key={pipeline.id}
              onClick={() => handlePipelineClick(pipeline.id)}
            >
              <PipelineCard cardVO={pipeline} />
            </div>
          );
        })}
      </div>
    </div>
  );
}
