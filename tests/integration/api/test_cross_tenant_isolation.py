"""Test cross-tenant isolation boundaries."""
import pytest
import uuid


@pytest.mark.asyncio
async def test_tenant_a_cannot_access_tenant_b_bots(auth_client_factory):
    """Tenant A cannot see or modify Tenant B's bots."""
    # Create two workspaces with different users
    client_a = await auth_client_factory(email="tenant_a@test.com")
    client_b = await auth_client_factory(email="tenant_b@test.com")
    
    # Tenant B creates a bot
    bot_resp = await client_b.post("/api/v1/platform/bots", json={
        "name": "Tenant B Bot",
        "enabled": True
    })
    assert bot_resp.status_code == 200
    bot_uuid = bot_resp.json()["data"]["uuid"]
    
    # Tenant A tries to access Tenant B's bot
    resp = await client_a.get(f"/api/v1/platform/bots/{bot_uuid}")
    assert resp.status_code == 404  # Not found (membership hiding)
    
    # Tenant A tries to delete Tenant B's bot
    resp = await client_a.delete(f"/api/v1/platform/bots/{bot_uuid}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_viewer_role_is_read_only(auth_client_factory):
    """Viewer role can read but not modify workspace resources."""
    owner = await auth_client_factory(email="owner@test.com")
    
    # Owner invites a viewer
    invite_resp = await owner.post("/api/v1/workspaces/current/invitations", json={
        "email": "viewer@test.com",
        "role": "viewer"
    })
    assert invite_resp.status_code == 200
    token = invite_resp.json()["data"]["token"]
    
    # Viewer accepts invitation
    viewer = await auth_client_factory(email="viewer@test.com")
    await viewer.post(f"/api/v1/workspaces/invitations/{token}/accept")
    
    # Viewer can read bots
    resp = await viewer.get("/api/v1/platform/bots")
    assert resp.status_code == 200
    
    # Viewer cannot create bots
    resp = await viewer.post("/api/v1/platform/bots", json={"name": "Test Bot"})
    assert resp.status_code == 403
    
    # Viewer cannot modify providers
    resp = await viewer.post("/api/v1/provider/providers", json={"name": "Test Provider"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_removed_member_loses_access(auth_client_factory):
    """Removed workspace member loses API access immediately."""
    owner = await auth_client_factory(email="owner@test.com")
    member = await auth_client_factory(email="member@test.com")
    
    # Owner invites member
    invite_resp = await owner.post("/api/v1/workspaces/current/invitations", json={
        "email": "member@test.com",
        "role": "developer"
    })
    token = invite_resp.json()["data"]["token"]
    await member.post(f"/api/v1/workspaces/invitations/{token}/accept")
    
    # Member can access workspace resources
    resp = await member.get("/api/v1/platform/bots")
    assert resp.status_code == 200
    
    # Owner removes member
    memberships = await owner.get("/api/v1/workspaces/current/members")
    member_uuid = next(m["uuid"] for m in memberships.json()["data"]["members"] 
                       if m["account_email"] == "member@test.com")
    await owner.delete(f"/api/v1/workspaces/current/members/{member_uuid}")
    
    # Member immediately loses access
    resp = await member.get("/api/v1/platform/bots")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_model_provider_credentials_isolated(auth_client_factory):
    """Model provider credentials are isolated per workspace."""
    client_a = await auth_client_factory(email="tenant_a@test.com")
    client_b = await auth_client_factory(email="tenant_b@test.com")
    
    # Tenant A creates provider with API key
    provider_resp = await client_a.post("/api/v1/provider/providers", json={
        "name": "OpenAI",
        "type": "openai",
        "api_key": "sk-tenant-a-secret-key"
    })
    assert provider_resp.status_code == 200
    provider_uuid = provider_resp.json()["data"]["uuid"]
    
    # Tenant B cannot see Tenant A's provider
    resp = await client_b.get(f"/api/v1/provider/providers/{provider_uuid}")
    assert resp.status_code == 404
    
    # Tenant B cannot list Tenant A's provider
    providers = await client_b.get("/api/v1/provider/providers")
    assert provider_uuid not in [p["uuid"] for p in providers.json()["data"]["providers"]]


@pytest.mark.asyncio  
async def test_websocket_messages_not_leaked_across_tenants(auth_client_factory, websocket_connect):
    """WebSocket messages are isolated to workspace."""
    client_a = await auth_client_factory(email="tenant_a@test.com")
    client_b = await auth_client_factory(email="tenant_b@test.com")
    
    # Both create bots
    bot_a_resp = await client_a.post("/api/v1/platform/bots", json={"name": "Bot A"})
    bot_b_resp = await client_b.post("/api/v1/platform/bots", json={"name": "Bot B"})
    
    bot_a_uuid = bot_a_resp.json()["data"]["uuid"]
    bot_b_uuid = bot_b_resp.json()["data"]["uuid"]
    
    # Connect WebSockets
    ws_a = await websocket_connect(client_a, f"/api/v1/pipeline/websocket/{bot_a_uuid}")
    ws_b = await websocket_connect(client_b, f"/api/v1/pipeline/websocket/{bot_b_uuid}")
    
    # Send message from Tenant A
    await ws_a.send_json({"message": "Hello from Tenant A"})
    
    # Tenant B should not receive Tenant A's message
    # (Only their own bot's response)
    import asyncio
    try:
        msg = await asyncio.wait_for(ws_b.receive_json(), timeout=1.0)
        assert "Tenant A" not in str(msg), "Message leaked across tenants!"
    except asyncio.TimeoutError:
        pass  # Expected - no cross-tenant messages


@pytest.mark.asyncio
async def test_invitation_token_workspace_scoped(auth_client_factory):
    """Invitation tokens are scoped to specific workspace."""
    workspace_a_owner = await auth_client_factory(email="owner_a@test.com")
    workspace_b_owner = await auth_client_factory(email="owner_b@test.com")
    
    # Workspace A creates invitation for user@test.com
    invite_resp = await workspace_a_owner.post("/api/v1/workspaces/current/invitations", json={
        "email": "user@test.com",
        "role": "developer"
    })
    token_a = invite_resp.json()["data"]["token"]
    
    # User tries to accept invitation in context of Workspace B
    user = await auth_client_factory(email="user@test.com")
    
    # Switch user's context to Workspace B
    workspaces = await user.get("/api/v1/workspaces")
    workspace_b_uuid = next(w["uuid"] for w in workspaces.json()["data"]["workspaces"] 
                            if w["created_by_account_email"] == "owner_b@test.com")
    
    # Accept with wrong workspace context should fail
    resp = await user.post(
        f"/api/v1/workspaces/invitations/{token_a}/accept",
        headers={"X-Workspace-ID": workspace_b_uuid}
    )
    assert resp.status_code in [400, 404]  # Token doesn't belong to this workspace
