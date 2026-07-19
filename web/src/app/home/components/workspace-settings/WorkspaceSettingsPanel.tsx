import { useCallback, useEffect, useMemo, useState } from 'react';
import { Copy, Loader2, Trash2, UserPlus, Users } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
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
  WorkspaceInvitation,
  WorkspaceMembership,
  WorkspaceRole,
} from '@/app/infra/entities/workspace';
import { backendClient } from '@/app/infra/http';
import {
  PanelBody,
  PanelToolbar,
} from '@/app/home/components/settings-dialog/panel-layout';
import WorkspaceSwitcher from './WorkspaceSwitcher';

interface WorkspaceSettingsPanelProps {
  active: boolean;
}

const ASSIGNABLE_ROLES: Exclude<WorkspaceRole, 'owner'>[] = [
  'admin',
  'developer',
  'operator',
  'viewer',
];

export default function WorkspaceSettingsPanel({
  active,
}: WorkspaceSettingsPanelProps) {
  const { t } = useTranslation();
  const [workspaceInfo, setWorkspaceInfo] = useState<CurrentWorkspace | null>(
    null,
  );
  const [members, setMembers] = useState<WorkspaceMembership[]>([]);
  const [invitations, setInvitations] = useState<WorkspaceInvitation[]>([]);
  const [loading, setLoading] = useState(false);
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
  const canInvite = !isCloudProjection && permissions.has('member.invite');
  const canUpdateMembers =
    !isCloudProjection && permissions.has('member.update_role');
  const canRemoveMembers =
    !isCloudProjection && permissions.has('member.remove');
  const canTransferOwner =
    !isCloudProjection && permissions.has('owner.transfer');

  const loadWorkspace = useCallback(async () => {
    setLoading(true);
    try {
      const current = await backendClient.getCurrentWorkspace();
      setWorkspaceInfo(current);

      const [memberResponse, invitationResponse] = await Promise.all([
        current.permissions.includes('member.view')
          ? backendClient.getWorkspaceMembers(current.workspace.uuid)
          : Promise.resolve({ members: [] }),
        current.workspace.source === 'local' &&
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
  }, [t]);

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
      const link = `${window.location.origin}/invitations/accept#token=${encodeURIComponent(response.token)}`;
      setOneTimeInviteLink(link);
      setInviteEmail('');
      await loadWorkspace();
      toast.success(t('workspace.invitationCreated'));
    } catch {
      toast.error(t('workspace.invitationCreateFailed'));
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
      <PanelToolbar>
        <div className="min-w-0">
          <p className="truncate text-sm font-medium">
            {workspaceInfo?.workspace.name ?? t('workspace.title')}
          </p>
          <p className="text-xs text-muted-foreground">
            {t(
              isCloudProjection
                ? 'workspace.cloudManagedDescription'
                : 'workspace.ossSingletonDescription',
            )}
          </p>
        </div>
        <WorkspaceSwitcher className="ml-auto" />
        {workspaceInfo && (
          <Badge variant="secondary">
            {t(`workspace.roles.${workspaceInfo.membership.role}`)}
          </Badge>
        )}
      </PanelToolbar>

      <PanelBody className="space-y-6">
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
            <div className="flex flex-col gap-2 sm:flex-row">
              <Input
                type="email"
                value={inviteEmail}
                onChange={(event) => setInviteEmail(event.target.value)}
                placeholder={t('workspace.emailPlaceholder')}
                className="flex-1"
              />
              <Select
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
                disabled={inviteLoading || !inviteEmail.trim()}
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
            <h3 className="text-sm font-semibold">{t('workspace.members')}</h3>
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
                    <ItemContent>
                      <ItemTitle>
                        {member.email}
                        {isSelf && (
                          <Badge variant="outline">{t('workspace.you')}</Badge>
                        )}
                      </ItemTitle>
                      <ItemDescription>
                        {t(`workspace.roles.${member.role}`)}
                      </ItemDescription>
                    </ItemContent>
                    <ItemActions>
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
                            {canTransferOwner && (
                              <SelectItem value="owner">
                                {t('workspace.transferOwnership')}
                              </SelectItem>
                            )}
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
    </>
  );
}
