"""Fire workflow schedule triggers through the bots this process runs.

A schedule names the bot that sends its messages. Only the process that runs
that bot (its Workspace placement) evaluates the schedule, so a schedule fires
once per minute slot without a separate lock.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .triggers import schedule_due, triggers_of


def _local(moment: datetime, name: str | None) -> datetime:
    try:
        return moment.astimezone(ZoneInfo(name or 'UTC'))
    except (ValueError, ZoneInfoNotFoundError):
        return moment.astimezone(timezone.utc)


class WorkflowScheduler:
    def __init__(self, ap):
        self.ap = ap
        self._fired: set[tuple[str, int, str]] = set()

    async def run(self) -> None:
        while True:
            now = datetime.now(timezone.utc)
            await asyncio.sleep(60 - now.second - now.microsecond / 1_000_000 + 0.5)
            try:
                await self.tick(datetime.now(timezone.utc).replace(second=0, microsecond=0))
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.ap.logger.warning(f'Workflow schedule pass failed: {type(exc).__name__}: {exc}')

    async def tick(self, moment: datetime) -> list[asyncio.Task]:
        """Start every schedule due in ``moment``'s minute; returns the started runs."""
        slot = moment.isoformat()
        self._fired = {key for key in self._fired if key[2] == slot}
        bots = {}
        for bot in tuple(getattr(self.ap.platform_mgr, 'bots', [])):
            if bot.enable:
                bots.setdefault(bot.workspace_uuid, {})[bot.bot_entity.uuid] = bot
        started = []
        for workspace_bots in bots.values():
            anchor = next(iter(workspace_bots.values()))
            workflows = await anchor._run_event_delivery(
                self.ap.workflow_service.workflows_with_trigger, anchor.execution_context, 'schedule'
            )
            for workflow in workflows:
                for index, trigger in enumerate(workflow.get('triggers') or []):
                    if trigger not in triggers_of(workflow, 'schedule'):
                        continue
                    bot = workspace_bots.get(trigger.get('bot_uuid'))
                    key = (workflow['uuid'], index, slot)
                    if bot is None or key in self._fired:
                        continue
                    try:
                        due = schedule_due(trigger, _local(moment, workflow.get('timezone')))
                    except ValueError:
                        continue
                    if not due:
                        continue
                    self._fired.add(key)
                    for target in trigger.get('targets') or []:
                        started.append(
                            asyncio.create_task(self._fire(bot, workflow, target, slot), name='workflow-schedule')
                        )
        return started

    async def _fire(self, bot, workflow, target, slot):
        try:
            await bot._run_event_delivery(
                bot.run_triggered_workflow,
                workflow,
                'schedule',
                {'target': target, 'scheduled_at': slot},
                target=target,
            )
        except Exception as exc:
            self.ap.logger.warning(
                f'Scheduled workflow {workflow["uuid"]} failed for {target.get("type")} {target.get("id")}: {exc}'
            )
