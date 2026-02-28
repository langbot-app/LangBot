"""API Chain Service - HTTP service for managing API chains"""

from __future__ import annotations

import uuid
from typing import Dict, Any, List
import sqlalchemy

from ....core import app
from ....entity.persistence import api_chain as api_chain_entity
# NOTE: uuid and sqlalchemy are kept for the read methods; mutations delegate to api_chain_mgr


class APIChainService:
    """Service for managing API chains"""

    ap: app.Application

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap

    async def get_api_chains(self) -> List[Dict[str, Any]]:
        """Get all API chains with their statuses"""
        result = await self.ap.persistence_mgr.execute_async(sqlalchemy.select(api_chain_entity.APIChain))

        chains = []
        for chain in result.all():
            # Get status for all providers in this chain
            status_result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.select(api_chain_entity.APIChainStatus).where(
                    api_chain_entity.APIChainStatus.chain_uuid == chain.uuid
                )
            )

            statuses = []
            for status in status_result.all():
                statuses.append(
                    {
                        'provider_uuid': status.provider_uuid,
                        'model_name': status.model_name,
                        'api_key_index': status.api_key_index,
                        'is_healthy': status.is_healthy,
                        'failure_count': status.failure_count,
                        'last_failure_time': status.last_failure_time.isoformat() if status.last_failure_time else None,
                        'last_success_time': status.last_success_time.isoformat() if status.last_success_time else None,
                        'last_health_check_time': status.last_health_check_time.isoformat()
                        if status.last_health_check_time
                        else None,
                        'last_error_message': status.last_error_message,
                        'health_check_last_failed': status.health_check_last_failed,
                    }
                )

            chains.append(
                {
                    'uuid': chain.uuid,
                    'name': chain.name,
                    'description': chain.description,
                    'chain_config': chain.chain_config,
                    'health_check_interval': chain.health_check_interval,
                    'health_check_enabled': chain.health_check_enabled,
                    'created_at': chain.created_at.isoformat() if chain.created_at else None,
                    'updated_at': chain.updated_at.isoformat() if chain.updated_at else None,
                    'statuses': statuses,
                }
            )

        return chains

    async def get_api_chain(self, chain_uuid: str) -> Dict[str, Any] | None:
        """Get a specific API chain"""
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(api_chain_entity.APIChain).where(api_chain_entity.APIChain.uuid == chain_uuid)
        )

        chain = result.first()
        if not chain:
            return None

        # Get status for all providers in the chain
        status_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(api_chain_entity.APIChainStatus).where(
                api_chain_entity.APIChainStatus.chain_uuid == chain_uuid
            )
        )

        statuses = []
        for status in status_result.all():
            statuses.append(
                {
                    'provider_uuid': status.provider_uuid,
                    'model_name': status.model_name,
                    'api_key_index': status.api_key_index,
                    'is_healthy': status.is_healthy,
                    'failure_count': status.failure_count,
                    'last_failure_time': status.last_failure_time.isoformat() if status.last_failure_time else None,
                    'last_success_time': status.last_success_time.isoformat() if status.last_success_time else None,
                    'last_health_check_time': status.last_health_check_time.isoformat()
                    if status.last_health_check_time
                    else None,
                    'last_error_message': status.last_error_message,
                    'health_check_last_failed': status.health_check_last_failed,
                }
            )

        return {
            'uuid': chain.uuid,
            'name': chain.name,
            'description': chain.description,
            'chain_config': chain.chain_config,
            'health_check_interval': chain.health_check_interval,
            'health_check_enabled': chain.health_check_enabled,
            'created_at': chain.created_at.isoformat() if chain.created_at else None,
            'updated_at': chain.updated_at.isoformat() if chain.updated_at else None,
            'statuses': statuses,
        }

    async def create_api_chain(self, chain_data: Dict[str, Any]) -> str:
        """Create a new API chain"""
        chain_data = dict(chain_data)
        chain_data.setdefault('uuid', str(uuid.uuid4()))
        chain_data.setdefault('chain_config', [])
        chain_data.setdefault('health_check_interval', 300)
        chain_data.setdefault('health_check_enabled', True)

        # Delegate to manager so in-memory state and health-check task are created
        await self.ap.api_chain_mgr.create_chain(chain_data)
        return chain_data['uuid']

    async def update_api_chain(self, chain_uuid: str, chain_data: Dict[str, Any]):
        """Update an existing API chain"""
        chain_data = dict(chain_data)
        chain_data.pop('uuid', None)
        chain_data.pop('created_at', None)
        chain_data.pop('updated_at', None)

        # Delegate to manager so in-memory state and health-check task are refreshed
        await self.ap.api_chain_mgr.update_chain(chain_uuid, chain_data)

    async def delete_api_chain(self, chain_uuid: str):
        """Delete an API chain"""
        # Delegate to manager which handles both DB deletion and memory/task cleanup
        await self.ap.api_chain_mgr.delete_chain(chain_uuid)

    async def test_api_chain(self, chain_uuid: str) -> Dict[str, Any]:
        """Test an API chain by making a simple request"""
        # This would make a test request through the chain
        # For now, just return success
        return {'success': True, 'message': 'API chain test not yet implemented'}
