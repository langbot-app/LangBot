import { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { httpClient } from '@/app/infra/http/HttpClient';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Trash2, Plus } from 'lucide-react';
import { toast } from 'sonner';

interface BotAdmin {
  id: number;
  launcher_type: string;
  launcher_id: string;
}

export default function BotAdminsPanel({ botId }: { botId: string }) {
  const { t } = useTranslation();
  const [admins, setAdmins] = useState<BotAdmin[]>([]);
  const [loading, setLoading] = useState(false);
  const [newType, setNewType] = useState('person');
  const [newId, setNewId] = useState('');
  const [adding, setAdding] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await httpClient.getBotAdmins(botId);
      setAdmins(res.admins ?? []);
    } finally {
      setLoading(false);
    }
  }, [botId]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleAdd() {
    if (!newId.trim()) return;
    setAdding(true);
    try {
      await httpClient.addBotAdmin(botId, newType, newId.trim());
      toast.success(t('bots.admins.addSuccess'));
      setNewId('');
      await load();
    } catch (e: any) {
      toast.error(t('bots.admins.addError') + (e?.msg ?? e?.message ?? ''));
    } finally {
      setAdding(false);
    }
  }

  async function handleDelete(id: number) {
    try {
      await httpClient.deleteBotAdmin(botId, id);
      toast.success(t('bots.admins.deleteSuccess'));
      setAdmins((prev) => prev.filter((a) => a.id !== id));
    } catch (e: any) {
      toast.error(t('bots.admins.deleteError') + (e?.msg ?? e?.message ?? ''));
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex gap-2 items-center">
        <Select value={newType} onValueChange={setNewType}>
          <SelectTrigger className="w-28 shrink-0">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="person">
              {t('bots.admins.typePerson')}
            </SelectItem>
            <SelectItem value="group">{t('bots.admins.typeGroup')}</SelectItem>
          </SelectContent>
        </Select>
        <Input
          className="flex-1"
          placeholder={t('bots.admins.placeholderId')}
          value={newId}
          onChange={(e) => setNewId(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleAdd()}
        />
        <Button
          size="sm"
          onClick={handleAdd}
          disabled={adding || !newId.trim()}
        >
          <Plus className="size-4 mr-1" />
          {t('bots.admins.addAdmin')}
        </Button>
      </div>

      {loading ? (
        <div className="text-sm text-muted-foreground py-4 text-center">
          {t('bots.sessionMonitor.loading')}
        </div>
      ) : admins.length === 0 ? (
        <div className="text-sm text-muted-foreground py-4 text-center">
          {t('bots.admins.noAdmins')}
        </div>
      ) : (
        <div className="border rounded-md overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/40">
                <th className="text-left px-3 py-2 font-medium text-muted-foreground w-28">
                  {t('bots.admins.launcherType')}
                </th>
                <th className="text-left px-3 py-2 font-medium text-muted-foreground">
                  {t('bots.admins.launcherId')}
                </th>
                <th className="w-10" />
              </tr>
            </thead>
            <tbody>
              {admins.map((admin) => (
                <tr
                  key={admin.id}
                  className="border-b last:border-0 hover:bg-muted/30"
                >
                  <td className="px-3 py-2">
                    <span className="px-1.5 py-0.5 rounded bg-muted text-xs">
                      {admin.launcher_type === 'person'
                        ? t('bots.admins.typePerson')
                        : t('bots.admins.typeGroup')}
                    </span>
                  </td>
                  <td className="px-3 py-2 font-mono">{admin.launcher_id}</td>
                  <td className="px-2 py-2">
                    <button
                      type="button"
                      className="text-muted-foreground hover:text-destructive transition-colors"
                      onClick={() => handleDelete(admin.id)}
                    >
                      <Trash2 className="size-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
