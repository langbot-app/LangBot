'use client';

import { useState, useEffect } from 'react';
import { Plus, Link2 } from 'lucide-react';
import { httpClient } from '@/app/infra/http/HttpClient';
import { APIChain, LLMModel, ModelProvider } from '@/app/infra/entities/api';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import APIChainForm from './APIChainForm';
import APIChainCard from './APIChainCard';

interface APIChainsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export default function APIChainsDialog({
  open,
  onOpenChange,
}: APIChainsDialogProps) {
  const { t } = useTranslation();

  const [chains, setChains] = useState<APIChain[]>([]);
  const [providers, setProviders] = useState<ModelProvider[]>([]);
  const [llmModels, setLlmModels] = useState<LLMModel[]>([]);
  const [chainFormOpen, setChainFormOpen] = useState(false);
  const [editingChainId, setEditingChainId] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      loadChains();
      loadProviders();
      loadLLMModels();
    }
  }, [open]);

  async function loadChains() {
    try {
      if (typeof httpClient.getAPIChains !== 'function') {
        console.error('httpClient.getAPIChains is not defined');
        toast.error(t('apiChains.loadError') + ': API method not found');
        return;
      }
      const resp = await httpClient.getAPIChains();
      setChains(resp.chains);
    } catch (err) {
      console.error('Failed to load API chains', err);
      toast.error(t('apiChains.loadError') + ': ' + (err as Error).message);
    }
  }

  async function loadProviders() {
    try {
      if (typeof httpClient.getModelProviders !== 'function') {
        console.error('httpClient.getModelProviders is not defined');
        return;
      }
      const resp = await httpClient.getModelProviders();
      setProviders(resp.providers);
    } catch (err) {
      console.error('Failed to load providers', err);
      toast.error((err as Error).message);
    }
  }

  async function loadLLMModels() {
    try {
      const resp = await httpClient.getProviderLLMModels();
      setLlmModels(resp.models);
    } catch (err) {
      console.error('Failed to load LLM models', err);
    }
  }

  function handleCreateChain() {
    setEditingChainId(null);
    setChainFormOpen(true);
  }

  function handleEditChain(chainId: string) {
    setEditingChainId(chainId);
    setChainFormOpen(true);
  }

  async function handleDeleteChain(chainId: string) {
    try {
      await httpClient.deleteAPIChain(chainId);
      toast.success(t('apiChains.chainDeleted'));
      loadChains();
    } catch (err) {
      toast.error(t('apiChains.chainDeleteError') + (err as Error).message);
    }
  }

  function handleFormClose() {
    setChainFormOpen(false);
    loadChains();
  }

  return (
    <>
      <Dialog
        open={open}
        onOpenChange={(newOpen) => {
          if (!newOpen && chainFormOpen) return;
          onOpenChange(newOpen);
        }}
      >
        <DialogContent className="overflow-hidden p-0 h-[80vh] flex flex-col !max-w-[37rem]">
          <DialogHeader className="px-6 pt-6 pb-0 flex-shrink-0">
            <DialogTitle>{t('apiChains.title')}</DialogTitle>
          </DialogHeader>

          <div className="flex-1 overflow-auto px-6 pb-6 mt-0">
            {/* Add Chain Button */}
            <div className="mb-3 flex justify-between items-center sticky top-0 bg-background py-2 z-10">
              <span className="text-sm text-muted-foreground">
                {chains.length === 0
                  ? t('apiChains.addChainHint')
                  : t('apiChains.chainCount', { count: chains.length })}
              </span>
              <Button
                size="sm"
                variant="outline"
                onClick={handleCreateChain}
              >
                <Plus className="h-4 w-4 mr-1" />
                {t('apiChains.addChain')}
              </Button>
            </div>

            {/* Chain List */}
            {chains.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                <Link2 className="h-12 w-12 mb-3 opacity-50" />
                <p className="text-sm">{t('apiChains.noChains')}</p>
              </div>
            ) : (
              chains.map((chain) => (
                <APIChainCard
                  key={chain.uuid}
                  chain={chain}
                  providers={providers}
                  llmModels={llmModels}
                  onEdit={() => handleEditChain(chain.uuid)}
                  onDelete={() => handleDeleteChain(chain.uuid)}
                />
              ))
            )}
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={chainFormOpen} onOpenChange={setChainFormOpen}>
        <DialogContent className="overflow-hidden p-0 h-[80vh] flex flex-col !max-w-[37rem]">
          <DialogHeader className="px-6 pt-6 pb-0 flex-shrink-0">
            <DialogTitle>
              {editingChainId
                ? t('apiChains.editChain')
                : t('apiChains.addChain')}
            </DialogTitle>
          </DialogHeader>
          <div className="flex-1 overflow-y-auto px-6 pb-6 pt-4">
            <APIChainForm
              chainId={editingChainId || undefined}
              providers={providers}
              llmModels={llmModels}
              onFormSubmit={handleFormClose}
              onFormCancel={() => setChainFormOpen(false)}
            />
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}

