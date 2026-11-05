import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from 'react';
import {
  Copy,
  ArrowRight,
  Loader2,
  Trash2,
  UserPlus,
  Users,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Item,
  ItemActions,
  ItemContent,
  ItemDescription,
  ItemMedia,
  ItemTitle,
} from '@/components/ui/item';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import type {
  CurrentWorkspace,
  WorkspaceSandboxSettings,
  E2BConfigInput,
  WorkspaceInvitation,
  WorkspaceMembership,
  WorkspaceRole,
} from '@/app/infra/entities/workspace';
import { backendClient, systemInfo } from '@/app/infra/http';
import {
  PanelBody,
  PanelToolbar,
} from '@/app/home/components/settings-dialog/panel-layout';
import WorkspacePlanBadge from './WorkspacePlanBadge';

const CloudPlansDialog = lazy(() => import('./CloudPlansDialog'));

interface WorkspaceSettingsPanelProps {
  active: boolean;
}

const ASSIGNABLE_ROLES: Exclude<WorkspaceRole, 'owner'>[] = [
  'admin',
  'developer',
  'operator',
  'viewer',
];

const SANDBOX_LABELS: Record<string, string> = {
  docker: 'Docker',
  e2b: 'E2B',
  nsjail: 'nsjail',
};

const MESSAGE_LANGUAGES: Record<string, string> = {
  en_US: 'English',
  zh_Hans: '简体中文',
  zh_Hant: '繁體中文',
  ja_JP: '日本語',
  es_ES: 'Español',
  ru_RU: 'Русский',
  th_TH: 'ไทย',
  vi_VN: 'Tiếng Việt',
};

export default function WorkspaceSettingsPanel({
  active,
}: WorkspaceSettingsPanelProps) {
  const { t } = useTranslation();
  const [plansOpen, setPlansOpen] = useState(false);
  const [workspaceInfo, setWorkspaceInfo] = useState<CurrentWorkspace | null>(
    null,
  );
  const [members, setMembers] = useState<WorkspaceMembership[]>([]);
  const [invitations, setInvitations] = useState<WorkspaceInvitation[]>([]);
  const [loading, setLoading] = useState(false);
  const [messageLanguage, setMessageLanguage] = useState('en_US');
  const [supportedLanguages, setSupportedLanguages] = useState<string[]>([]);
  const [savingLanguage, setSavingLanguage] = useState(false);
  const [sandbox, setSandbox] = useState<WorkspaceSandboxSettings | null>(null);
  const [savingSandbox, setSavingSandbox] = useState(false);
  const [draftBackend, setDraftBackend] = useState('');
  const [detectedBackends, setDetectedBackends] = useState<
    WorkspaceSandboxSettings['backends']
  >([]);
  const [e2bDraft, setE2bDraft] = useState<E2BConfigInput>({
    api_url: '',
    sandbox_url: '',
    api_key: '',
    template: 'base',
  });
  const [e2bReady, setE2bReady] = useState(false);
  const resetSandboxDraft = useCallback(
    (settings: WorkspaceSandboxSettings) => {
      setDraftBackend(settings.effective_backend || '');
      setDetectedBackends(settings.backends);
      setE2bDraft({
        api_url: settings.e2b?.api_url || '',
        sandbox_url: settings.e2b?.sandbox_url || '',
        template: settings.e2b?.template || 'base',
        api_key: '',
      });
      setE2bReady(
        settings.backends.some(
          (item) =>
            item.name === 'e2b' && item.available && item.template_validated,
        ),
      );
    },
    [],
  );

  const [checkingSandbox, setCheckingSandbox] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] =
    useState<Exclude<WorkspaceRole, 'owner'>>('viewer');
  const [inviteLoading, setInviteLoading] = useState(false);
  const [oneTimeInviteLink, setOneTimeInviteLink] = useState<string | null>(
    null,
  );

  const permissions = useMemo(
    () => new Set(workspaceInfo?.permissions ?? []),
    [workspaceInfo],
  );
  const isCloudProjection =
    workspaceInfo?.workspace.source === 'cloud_projection';
  const canViewMembers = permissions.has('member.view');
  const canInvite = permissions.has('member.invite');
  const canUpdateMembers = permissions.has('member.update_role');
  const canRemoveMembers = permissions.has('member.remove');
  // Cloud plans cap members; pending invitations reserve seats too, matching
  // the backend check. Self-hosted workspaces report no member limit.
  const maxMembers = isCloudProjection
    ? (workspaceInfo?.limitation?.max_members ?? -1)
    : -1;
  const memberLimitReached =
    canViewMembers &&
    maxMembers >= 0 &&
    members.length + invitations.length >= maxMembers;

  const loadWorkspace = useCallback(async () => {
    setLoading(true);
    try {
      const [current, languageSettings, sandboxSettings] = await Promise.all([
        backendClient.getCurrentWorkspace(),
        backendClient.getWorkspaceLanguage(),
        backendClient.getWorkspaceSandbox(),
      ]);
      setWorkspaceInfo(current);
      setSandbox(sandboxSettings);
      resetSandboxDraft(sandboxSettings);
      setMessageLanguage(languageSettings.language);
      setSupportedLanguages(languageSettings.supported_languages);

      const [memberResponse, invitationResponse] = await Promise.all([
        current.permissions.includes('member.view')
          ? backendClient.getWorkspaceMembers(current.workspace.uuid)
          : Promise.resolve({ members: [] }),
        current.permissions.includes('member.invite')
          ? backendClient.getWorkspaceInvitations(current.workspace.uuid)
          : Promise.resolve({ invitations: [] }),
      ]);
      setMembers(memberResponse.members);
      setInvitations(invitationResponse.invitations);
    } catch {
      toast.error(t('workspace.loadFailed'));
    } finally {
      setLoading(false);
    }
  }, [t, resetSandboxDraft]);

  const sandboxDirty =
    draftBackend !== (sandbox?.effective_backend || '') ||
    (draftBackend === 'e2b' &&
      (e2bDraft.api_url !== (sandbox?.e2b?.api_url || '') ||
        e2bDraft.sandbox_url !== (sandbox?.e2b?.sandbox_url || '') ||
        e2bDraft.template !== (sandbox?.e2b?.template || 'base') ||
        Boolean(e2bDraft.api_key)));

  function editE2b(field: keyof E2BConfigInput, value: string) {
    setE2bDraft((current) => ({ ...current, [field]: value }));
    setE2bReady(false);
    setDetectedBackends((current) =>
      current.map((item) =>
        item.name === 'e2b'
          ? {
              ...item,
              available: false,
              reason: 'not_checked',
            }
          : item,
      ),
    );
  }

  async function refreshSandbox() {
    setCheckingSandbox(true);
    try {
      const result =
        draftBackend === 'e2b'
          ? await backendClient.checkWorkspaceSandbox(e2bDraft)
          : await backendClient.getWorkspaceSandbox(true);
      setDetectedBackends(result.backends);
      setE2bReady(
        result.backends.some(
          (item) =>
            item.name === 'e2b' && item.available && item.template_validated,
        ),
      );
    } catch {
      if (draftBackend === 'e2b') {
        setE2bReady(false);
        setDetectedBackends((current) =>
          current.map((item) =>
            item.name === 'e2b'
              ? { ...item, available: false, reason: 'invalid_configuration' }
              : item,
          ),
        );
      }
      toast.error(t('workspaceSandbox.loadFailed'));
    } finally {
      setCheckingSandbox(false);
    }
  }

  async function saveSandbox() {
    setSavingSandbox(true);
    try {
      const result = await backendClient.setWorkspaceSandbox(
        draftBackend,
        draftBackend === 'e2b' ? e2bDraft : undefined,
      );
      setSandbox(result);
      resetSandboxDraft(result);
      toast.success(t('workspaceSandbox.saved'));
    } catch {
      toast.error(t('workspaceSandbox.saveFailed'));
    } finally {
      setSavingSandbox(false);
    }
  }

  async function saveLanguage(locale: string) {
    setSavingLanguage(true);
    try {
      const result = await backendClient.setWorkspaceLanguage(locale);
      setMessageLanguage(result.language);
      toast.success(t('workspaceLanguage.saved'));
    } catch {
      toast.error(t('workspaceLanguage.saveFailed'));
    } finally {
      setSavingLanguage(false);
    }
  }

  useEffect(() => {
    if (active) void loadWorkspace();
  }, [active, loadWorkspace]);

  async function createInvitation() {
    if (!workspaceInfo || !inviteEmail.trim()) return;
    setInviteLoading(true);
    try {
      const response = await backendClient.createWorkspaceInvitation(
        workspaceInfo.workspace.uuid,
        inviteEmail.trim(),
        inviteRole,
      );
      setOneTimeInviteLink(response.link);
      setInviteEmail('');
      await loadWorkspace();
      toast.success(t(`workspace.delivery.${response.delivery.status}`));
    } catch (error) {
      if ((error as { code?: unknown })?.code === 'member_limit_reached') {
        toast.error(t('workspace.memberLimitReachedToast'));
        await loadWorkspace();
      } else {
        toast.error(t('workspace.invitationCreateFailed'));
      }
    } finally {
      setInviteLoading(false);
    }
  }

  async function copyInvitationLink() {
    if (!oneTimeInviteLink) return;
    await navigator.clipboard.writeText(oneTimeInviteLink);
    toast.success(t('workspace.invitationCopied'));
  }

  async function updateMemberRole(
    member: WorkspaceMembership,
    role: WorkspaceRole,
  ) {
    if (!workspaceInfo || member.role === role) return;
    try {
      await backendClient.updateWorkspaceMemberRole(
        workspaceInfo.workspace.uuid,
        member.account_uuid,
        role,
      );
      await loadWorkspace();
      toast.success(t('workspace.memberUpdated'));
    } catch {
      toast.error(t('workspace.memberUpdateFailed'));
    }
  }

  async function removeMember(member: WorkspaceMembership) {
    if (!workspaceInfo) return;
    if (!window.confirm(t('workspace.removeMemberConfirm'))) return;
    try {
      await backendClient.removeWorkspaceMember(
        workspaceInfo.workspace.uuid,
        member.account_uuid,
      );
      await loadWorkspace();
      toast.success(t('workspace.memberRemoved'));
    } catch {
      toast.error(t('workspace.memberRemoveFailed'));
    }
  }

  async function revokeInvitation(invitation: WorkspaceInvitation) {
    if (!workspaceInfo) return;
    try {
      await backendClient.revokeWorkspaceInvitation(
        workspaceInfo.workspace.uuid,
        invitation.uuid,
      );
      await loadWorkspace();
      toast.success(t('workspace.invitationRevoked'));
    } catch {
      toast.error(t('workspace.invitationRevokeFailed'));
    }
  }

  if (loading && !workspaceInfo) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <Loader2 className="size-6 animate-spin" />
      </div>
    );
  }

  return (
    <>
      <PanelToolbar className="gap-4 py-4">
        <div className="min-w-0 flex-1 basis-56 space-y-1.5">
          <div className="flex min-w-0 items-center gap-2">
            <p className="truncate text-sm font-semibold">
              {workspaceInfo?.workspace.name ?? t('workspace.title')}
            </p>
            {workspaceInfo && (
              <Badge
                variant="secondary"
                className="shrink-0 text-[11px] font-normal"
              >
                {t(`workspace.roles.${workspaceInfo.membership.role}`)}
              </Badge>
            )}
          </div>
          <p className="text-xs text-muted-foreground">
            {t(
              isCloudProjection
                ? 'workspace.cloudManagedDescription'
                : 'workspace.ossSingletonDescription',
            )}
          </p>
        </div>
        {isCloudProjection && workspaceInfo && (
          <div className="ml-auto flex max-w-full flex-wrap items-center justify-end gap-3">
            <div className="space-y-1 text-right">
              <p className="text-[11px] text-muted-foreground">
                {t('workspace.currentPlan')}
              </p>
              <WorkspacePlanBadge planName={workspaceInfo.plan_name} />
            </div>
            <Button
              size="sm"
              className="shrink-0"
              onClick={() => setPlansOpen(true)}
            >
              {t('cloudPlans.title')}
              <ArrowRight className="size-3.5" />
            </Button>
          </div>
        )}
      </PanelToolbar>

      <PanelBody className="space-y-6">
        <section className="space-y-3">
          <div>
            <h3 id="workspace-language-label" className="text-sm font-semibold">
              {t('workspaceLanguage.label')}
            </h3>
            <p
              id="workspace-language-description"
              className="text-xs text-muted-foreground"
            >
              {t('workspaceLanguage.description')}
            </p>
          </div>
          <Select
            value={messageLanguage}
            onValueChange={saveLanguage}
            disabled={
              loading || savingLanguage || !permissions.has('workspace.update')
            }
          >
            <SelectTrigger
              className="w-full sm:w-64"
              aria-labelledby="workspace-language-label"
              aria-describedby="workspace-language-description"
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {supportedLanguages.map((locale) => (
                <SelectItem key={locale} value={locale}>
                  {MESSAGE_LANGUAGES[locale] || locale}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </section>
        <section className="space-y-3">
          <div>
            <h3 id="workspace-sandbox-label" className="text-sm font-semibold">
              {t('workspaceSandbox.label')}
            </h3>
            <p
              id="workspace-sandbox-description"
              className="text-xs text-muted-foreground"
            >
              {t('workspaceSandbox.description')}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Select
              value={draftBackend}
              onValueChange={setDraftBackend}
              disabled={
                loading ||
                savingSandbox ||
                checkingSandbox ||
                !permissions.has('workspace.update')
              }
            >
              <SelectTrigger
                className="w-full sm:w-64"
                aria-labelledby="workspace-sandbox-label"
                aria-describedby="workspace-sandbox-description"
              >
                <SelectValue
                  placeholder={t('workspaceSandbox.noEnvironment')}
                />
              </SelectTrigger>
              <SelectContent>
                {detectedBackends.map((item) => (
                  <SelectItem
                    key={item.name}
                    value={item.name}
                    disabled={!item.available}
                  >
                    {SANDBOX_LABELS[item.name] || item.name}
                    {!item.available &&
                      ` (${t(`workspaceSandbox.reasons.${item.reason || 'environment_unavailable'}`)})`}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button
              variant="outline"
              size="sm"
              onClick={refreshSandbox}
              disabled={checkingSandbox || savingSandbox || loading}
            >
              {checkingSandbox && <Loader2 className="size-3.5 animate-spin" />}
              {t('workspaceSandbox.refresh')}
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">
            {t('workspaceSandbox.current', {
              backend:
                SANDBOX_LABELS[sandbox?.effective_backend || ''] ||
                sandbox?.effective_backend ||
                '—',
            })}
            {sandboxDirty && (
              <span className="ml-2">{t('workspaceSandbox.unsaved')}</span>
            )}
          </p>
          {draftBackend !== 'e2b' && sandbox?.e2b_configurable !== false && (
            <Button
              variant="link"
              size="sm"
              onClick={() => setDraftBackend('e2b')}
              disabled={
                loading ||
                savingSandbox ||
                checkingSandbox ||
                !permissions.has('workspace.update')
              }
            >
              {t('workspaceSandbox.configureE2b')}
            </Button>
          )}
          {draftBackend === 'e2b' && (
            <div className="space-y-3 rounded-md border p-3">
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="space-y-1">
                  <Label htmlFor="e2b-api-url">
                    {t('workspaceSandbox.apiUrl')}
                  </Label>
                  <Input
                    id="e2b-api-url"
                    type="url"
                    value={e2bDraft.api_url}
                    placeholder="https://api.example.com"
                    onChange={(event) => editE2b('api_url', event.target.value)}
                    disabled={
                      savingSandbox ||
                      checkingSandbox ||
                      !permissions.has('workspace.update') ||
                      sandbox?.e2b_configurable === false
                    }
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="e2b-sandbox-url">
                    {t('workspaceSandbox.sandboxUrl')}
                  </Label>
                  <Input
                    id="e2b-sandbox-url"
                    type="url"
                    value={e2bDraft.sandbox_url}
                    placeholder="https://sandbox.example.com"
                    onChange={(event) =>
                      editE2b('sandbox_url', event.target.value)
                    }
                    disabled={
                      savingSandbox ||
                      checkingSandbox ||
                      !permissions.has('workspace.update') ||
                      sandbox?.e2b_configurable === false
                    }
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="e2b-api-key">API Key</Label>
                  <Input
                    id="e2b-api-key"
                    type="password"
                    autoComplete="new-password"
                    value={e2bDraft.api_key || ''}
                    placeholder={t(
                      sandbox?.e2b?.api_key_configured
                        ? 'workspaceSandbox.keyConfigured'
                        : 'workspaceSandbox.keyRequired',
                    )}
                    onChange={(event) => editE2b('api_key', event.target.value)}
                    disabled={
                      savingSandbox ||
                      checkingSandbox ||
                      !permissions.has('workspace.update') ||
                      sandbox?.e2b_configurable === false
                    }
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="e2b-template">
                    {t('workspaceSandbox.template')}
                  </Label>
                  <Input
                    id="e2b-template"
                    value={e2bDraft.template}
                    placeholder="base"
                    onChange={(event) =>
                      editE2b('template', event.target.value)
                    }
                    disabled={
                      savingSandbox ||
                      checkingSandbox ||
                      !permissions.has('workspace.update') ||
                      sandbox?.e2b_configurable === false
                    }
                  />
                </div>
              </div>
              <p className="text-xs text-muted-foreground">
                {t('workspaceSandbox.keyHelp')}
              </p>
              {e2bReady && (
                <p className="text-xs text-green-600">
                  {t('workspaceSandbox.templateVerified')}
                </p>
              )}
              {!e2bReady && (
                <p role="status" className="text-xs text-muted-foreground">
                  {t('workspaceSandbox.checkHint')}
                </p>
              )}
            </div>
          )}
          {detectedBackends
            .filter((item) => !item.available)
            .map((item) => (
              <p
                key={item.name}
                className="text-xs text-muted-foreground"
                role="status"
              >
                {SANDBOX_LABELS[item.name] || item.name}:{' '}
                {t(
                  `workspaceSandbox.reasons.${item.reason || 'environment_unavailable'}`,
                )}
              </p>
            ))}
          <div className="flex gap-2">
            <Button
              size="sm"
              onClick={saveSandbox}
              disabled={
                loading ||
                savingSandbox ||
                checkingSandbox ||
                !sandboxDirty ||
                !permissions.has('workspace.update') ||
                !detectedBackends.some(
                  (item) => item.name === draftBackend && item.available,
                ) ||
                (draftBackend === 'e2b' && !e2bReady)
              }
            >
              {savingSandbox && <Loader2 className="size-3.5 animate-spin" />}
              {t('workspaceSandbox.confirm')}
            </Button>
            {sandboxDirty && (
              <Button
                size="sm"
                variant="outline"
                disabled={savingSandbox || checkingSandbox}
                onClick={() => sandbox && resetSandboxDraft(sandbox)}
              >
                {t('workspaceSandbox.cancel')}
              </Button>
            )}
          </div>
          {detectedBackends.some(
            (item) =>
              item.name === draftBackend && item.managed_processes === false,
          ) && (
            <p role="status" className="text-xs text-muted-foreground">
              {t('workspaceSandbox.noManagedProcesses')}
            </p>
          )}
          {sandbox?.backend &&
            !detectedBackends.some(
              (item) => item.name === sandbox.backend && item.available,
            ) && (
              <p role="status" className="text-xs text-destructive">
                {t('workspaceSandbox.unavailable')}
              </p>
            )}
        </section>
        {canInvite && (
          <section className="space-y-3">
            <div>
              <h3 className="text-sm font-semibold">
                {t('workspace.inviteMember')}
              </h3>
              <p className="text-xs text-muted-foreground">
                {t('workspace.inviteDescription')}
              </p>
            </div>
            {memberLimitReached && (
              <div
                role="status"
                data-testid="workspace-member-limit-cta"
                className="flex flex-col gap-3 rounded-lg border border-amber-500/30 bg-amber-500/5 p-3 sm:flex-row sm:items-center"
              >
                <p className="flex-1 text-xs text-muted-foreground">
                  {t('workspace.memberLimitReached', { max: maxMembers })}
                </p>
                <Button
                  size="sm"
                  className="shrink-0"
                  onClick={() => setPlansOpen(true)}
                >
                  {t('workspace.upgradePlan')}
                  <ArrowRight className="size-3.5" />
                </Button>
              </div>
            )}
            {systemInfo?.edition === 'cloud' &&
              !isCloudProjection &&
              systemInfo.cloud_service_url && (
                <div className="flex flex-col gap-2 rounded-lg border bg-muted/40 p-3 text-xs sm:flex-row sm:items-center sm:justify-between">
                  <p className="text-muted-foreground">
                    {t('workspace.dedicatedSpaceMembersHint')}
                  </p>
                  <Button size="sm" variant="outline" asChild>
                    <a
                      href={`${systemInfo.cloud_service_url.replace(/\/+$/, '')}/cloud`}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      {t('workspace.manageOnSpace')}
                      <ArrowRight className="size-3.5" />
                    </a>
                  </Button>
                </div>
              )}
            <div className="flex flex-col gap-2 sm:flex-row">
              <Input
                type="email"
                value={inviteEmail}
                onChange={(event) => setInviteEmail(event.target.value)}
                placeholder={t('workspace.emailPlaceholder')}
                className="flex-1"
                disabled={memberLimitReached}
              />
              <Select
                disabled={memberLimitReached}
                value={inviteRole}
                onValueChange={(value) =>
                  setInviteRole(value as Exclude<WorkspaceRole, 'owner'>)
                }
              >
                <SelectTrigger className="w-full sm:w-36">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ASSIGNABLE_ROLES.map((role) => (
                    <SelectItem key={role} value={role}>
                      {t(`workspace.roles.${role}`)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button
                onClick={createInvitation}
                disabled={
                  memberLimitReached || inviteLoading || !inviteEmail.trim()
                }
              >
                {inviteLoading ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : (
                  <UserPlus className="size-4" />
                )}
                {t('workspace.createInvitation')}
              </Button>
            </div>

            {oneTimeInviteLink && (
              <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-3">
                <p className="mb-2 text-xs text-muted-foreground">
                  {t('workspace.oneTimeLinkWarning')}
                </p>
                <div className="flex gap-2">
                  <Input value={oneTimeInviteLink} readOnly />
                  <Button
                    variant="outline"
                    size="icon"
                    onClick={copyInvitationLink}
                    aria-label={t('workspace.copyInvitation')}
                  >
                    <Copy className="size-4" />
                  </Button>
                </div>
              </div>
            )}
          </section>
        )}

        {canViewMembers && (
          <section className="space-y-3">
            <div className="flex items-center justify-between gap-3">
              <h3 className="text-sm font-semibold">
                {t('workspace.members')}
              </h3>
            </div>
            <div className="space-y-2">
              {members.map((member) => {
                const isSelf =
                  member.account_uuid ===
                  workspaceInfo?.membership.account_uuid;
                return (
                  <Item
                    key={member.uuid}
                    size="sm"
                    variant="muted"
                    className="rounded-lg"
                  >
                    <ItemMedia variant="icon">
                      <Users className="size-4" />
                    </ItemMedia>
                    <ItemContent className="min-w-0">
                      <ItemTitle>
                        {member.display_name}
                        {isSelf && (
                          <Badge variant="outline">{t('workspace.you')}</Badge>
                        )}
                      </ItemTitle>
                      <ItemDescription className="flex flex-wrap items-center gap-x-1.5 gap-y-0.5">
                        <span className="break-all">{member.email}</span>
                        <span aria-hidden="true">·</span>
                        <span>{t(`workspace.roles.${member.role}`)}</span>
                      </ItemDescription>
                    </ItemContent>
                    <ItemActions className="max-sm:basis-full max-sm:justify-end max-sm:pl-10">
                      {canUpdateMembers && member.role !== 'owner' && (
                        <Select
                          value={member.role}
                          onValueChange={(role) =>
                            void updateMemberRole(member, role as WorkspaceRole)
                          }
                        >
                          <SelectTrigger size="sm" className="w-32">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {ASSIGNABLE_ROLES.map((role) => (
                              <SelectItem key={role} value={role}>
                                {t(`workspace.roles.${role}`)}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      )}
                      {canRemoveMembers &&
                        !isSelf &&
                        member.role !== 'owner' && (
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => void removeMember(member)}
                            aria-label={t('workspace.removeMember')}
                          >
                            <Trash2 className="size-4" />
                          </Button>
                        )}
                    </ItemActions>
                  </Item>
                );
              })}
            </div>
          </section>
        )}

        {canInvite && invitations.length > 0 && (
          <section className="space-y-3">
            <h3 className="text-sm font-semibold">
              {t('workspace.pendingInvitations')}
            </h3>
            <div className="space-y-2">
              {invitations.map((invitation) => (
                <Item
                  key={invitation.uuid}
                  size="sm"
                  variant="outline"
                  className="rounded-lg"
                >
                  <ItemContent>
                    <ItemTitle>{invitation.normalized_email}</ItemTitle>
                    <ItemDescription>
                      {t(`workspace.roles.${invitation.role}`)} ·{' '}
                      {t('workspace.expiresAt', {
                        date: new Date(invitation.expires_at).toLocaleString(),
                      })}
                    </ItemDescription>
                  </ItemContent>
                  <ItemActions>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => void revokeInvitation(invitation)}
                      aria-label={t('workspace.revokeInvitation')}
                    >
                      <Trash2 className="size-4" />
                    </Button>
                  </ItemActions>
                </Item>
              ))}
            </div>
          </section>
        )}
      </PanelBody>
      {isCloudProjection && workspaceInfo && plansOpen && (
        <Suspense fallback={null}>
          <CloudPlansDialog
            key={workspaceInfo.workspace.uuid}
            open={plansOpen}
            onOpenChange={setPlansOpen}
            workspace={workspaceInfo}
            spaceURL={systemInfo.cloud_service_url}
          />
        </Suspense>
      )}
    </>
  );
}
