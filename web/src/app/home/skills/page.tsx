'use client';

import CreateCardComponent from '@/app/infra/basic-component/create-card-component/CreateCardComponent';
import styles from './skills.module.css';
import { useTranslation } from 'react-i18next';
import { useEffect, useState } from 'react';
import { SkillCardVO } from '@/app/home/skills/components/skill-card/SkillCardVO';
import SkillCard from '@/app/home/skills/components/skill-card/SkillCard';
import SkillDetailDialog from '@/app/home/skills/SkillDetailDialog';
import { httpClient } from '@/app/infra/http/HttpClient';
import { Skill } from '@/app/infra/entities/api';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Search } from 'lucide-react';

export default function SkillsPage() {
  const { t } = useTranslation();
  const [skillList, setSkillList] = useState<SkillCardVO[]>([]);
  const [filteredSkillList, setFilteredSkillList] = useState<SkillCardVO[]>([]);
  const [selectedSkillId, setSelectedSkillId] = useState<string>('');
  const [detailDialogOpen, setDetailDialogOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState<string>('all');

  useEffect(() => {
    getSkillList();
  }, []);

  useEffect(() => {
    filterSkills();
  }, [skillList, searchQuery, typeFilter]);

  async function getSkillList() {
    try {
      const resp = await httpClient.getSkills();
      setSkillList(
        resp.skills.map((skill: Skill) => {
          const currentTime = new Date();
          const updatedAt = skill.updated_at
            ? new Date(skill.updated_at)
            : currentTime;
          const lastUpdatedTimeAgo = Math.floor(
            (currentTime.getTime() - updatedAt.getTime()) / 1000 / 60 / 60 / 24,
          );

          const lastUpdatedTimeAgoText =
            lastUpdatedTimeAgo > 0
              ? `${t('knowledge.updateTime')} ${lastUpdatedTimeAgo} ${t('knowledge.daysAgo')}`
              : `${t('knowledge.updateTime')} ${t('knowledge.today')}`;

          return new SkillCardVO({
            id: skill.uuid || '',
            name: skill.name,
            description: skill.description,
            type: skill.type,
            isEnabled: skill.is_enabled ?? true,
            isBuiltin: skill.is_builtin ?? false,
            author: skill.author,
            version: skill.version,
            tags: skill.tags,
            lastUpdatedTimeAgo: lastUpdatedTimeAgoText,
          });
        }),
      );
    } catch (error) {
      console.error('Failed to load skills:', error);
    }
  }

  function filterSkills() {
    let filtered = [...skillList];

    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(
        (skill) =>
          skill.name.toLowerCase().includes(query) ||
          skill.description.toLowerCase().includes(query),
      );
    }

    if (typeFilter !== 'all') {
      filtered = filtered.filter((skill) => skill.type === typeFilter);
    }

    setFilteredSkillList(filtered);
  }

  const handleSkillCardClick = (skillId: string) => {
    setSelectedSkillId(skillId);
    setDetailDialogOpen(true);
  };

  const handleCreateSkillClick = () => {
    setSelectedSkillId('');
    setDetailDialogOpen(true);
  };

  const handleFormCancel = () => {
    setDetailDialogOpen(false);
  };

  const handleSkillDeleted = () => {
    getSkillList();
    setDetailDialogOpen(false);
  };

  const handleNewSkillCreated = (newSkillId: string) => {
    getSkillList();
    setSelectedSkillId(newSkillId);
    setDetailDialogOpen(true);
  };

  const handleSkillUpdated = () => {
    getSkillList();
  };

  return (
    <div>
      <SkillDetailDialog
        open={detailDialogOpen}
        onOpenChange={setDetailDialogOpen}
        skillId={selectedSkillId || undefined}
        onFormCancel={handleFormCancel}
        onSkillDeleted={handleSkillDeleted}
        onNewSkillCreated={handleNewSkillCreated}
        onSkillUpdated={handleSkillUpdated}
      />

      <div className={styles.filterContainer}>
        <div className={`${styles.searchInput} relative`}>
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder={t('skills.searchSkills')}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9"
          />
        </div>
        <Select value={typeFilter} onValueChange={setTypeFilter}>
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder={t('skills.filterByType')} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t('skills.allTypes')}</SelectItem>
            <SelectItem value="skill">{t('skills.typeSkill')}</SelectItem>
            <SelectItem value="workflow">{t('skills.typeWorkflow')}</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className={styles.skillsListContainer}>
        <CreateCardComponent
          width={'100%'}
          height={'10rem'}
          plusSize={'90px'}
          onClick={handleCreateSkillClick}
        />

        {filteredSkillList.map((skill) => {
          return (
            <div key={skill.id} onClick={() => handleSkillCardClick(skill.id)}>
              <SkillCard skillCardVO={skill} />
            </div>
          );
        })}
      </div>

      {filteredSkillList.length === 0 && skillList.length === 0 && (
        <div className="text-center text-muted-foreground py-8">
          {t('skills.noSkills')}
        </div>
      )}
    </div>
  );
}
