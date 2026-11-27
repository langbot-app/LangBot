"""Unit tests for ApplicationAPI operation documentation and exposure metadata."""

from __future__ import annotations

import re

import pytest

from langbot.pkg.api.application.api import ApplicationAPI
from langbot.pkg.api.application.contracts import Operation
from langbot.pkg.api.application.operation_docs import DOMAINS, OPERATION_DOCS, OperationDoc, get_operation_doc
from langbot.pkg.api.context import PrincipalType


@pytest.fixture(scope='module')
def application_api() -> ApplicationAPI:
    return ApplicationAPI(None)


@pytest.fixture(scope='module')
def all_application_operations(application_api: ApplicationAPI) -> list[Operation]:
    # Inspect the actual default registry for checks that need the typed specs.
    return list(application_api._operations.values())


@pytest.fixture(scope='module')
def catalog_by_id(application_api: ApplicationAPI) -> dict[str, dict]:
    catalog = application_api.operation_catalog()
    by_id = {item['id']: item for item in catalog}
    assert len(by_id) == len(catalog), 'The published catalog must not duplicate operation IDs'
    return by_id


@pytest.fixture(scope='module')
def operations_by_id(all_application_operations: list[Operation]) -> dict[str, Operation]:
    return {op.operation_id: op for op in all_application_operations}


@pytest.fixture(scope='module')
def in_scope_operation_ids(operations_by_id: dict[str, Operation]) -> set[str]:
    in_scope = set()
    for op_id in operations_by_id:
        if op_id in {'plugin.permissions.get', 'plugin.permissions.update'}:
            continue
        if op_id.startswith('monitoring.export.'):
            continue
        if (
            op_id.startswith('monitoring.')
            or op_id == 'stats.basic'
            or op_id == 'task.get'
            or op_id == 'workspace.language.get'
            or op_id.startswith('workspace.sandbox.')
            or op_id.startswith('bot.')
            or op_id.startswith('adapter.')
            or op_id.startswith('agent.')
            or op_id.startswith('pipeline.')
            or op_id.startswith('knowledge.')
            or op_id.startswith('plugin.')
            or op_id.startswith('mcp.')
            or op_id.startswith('skill.')
            or op_id == 'extension.list'
            or op_id.startswith('tool.')
            or op_id.startswith('model.')
            or op_id.startswith('provider.')
            or op_id.startswith('requester.')
            or op_id.startswith('artifact.')
        ):
            in_scope.add(op_id)
    return in_scope


def test_in_scope_operations_coverage(in_scope_operation_ids: set[str], catalog_by_id: dict[str, dict]):
    published_ids = set(catalog_by_id)
    assert in_scope_operation_ids <= published_ids, 'Registered documented operations must be published'
    missing = in_scope_operation_ids - OPERATION_DOCS.keys()
    assert not missing, f'Missing documentation for operations: {missing}'
    extra = OPERATION_DOCS.keys() - in_scope_operation_ids
    assert not extra, f'Unknown or out-of-scope operation docs: {extra}'


def test_out_of_scope_operations_are_none(in_scope_operation_ids: set[str], catalog_by_id: dict[str, dict]):
    out_of_scope_ids = catalog_by_id.keys() - in_scope_operation_ids
    assert out_of_scope_ids, 'The catalog must exercise the default non-exposure policy'
    for op_id in out_of_scope_ids:
        assert catalog_by_id[op_id]['exposure'] == 'none', f'Out of scope operation {op_id} was exposed'


def test_summary_and_description_constraints():
    for op_id, doc in OPERATION_DOCS.items():
        assert isinstance(doc, OperationDoc)
        assert doc.summary, f'{op_id} summary must not be empty'
        assert len(doc.summary) <= 120, f"{op_id} summary exceeds 120 chars: {len(doc.summary)} ('{doc.summary}')"
        assert doc.description, f'{op_id} description must not be empty'
        assert len(doc.description) > 10, f'{op_id} description too short'
        assert 'zh_Hans' in doc.label and doc.label['zh_Hans'], f'{op_id} missing zh_Hans label'
        assert 'en_US' in doc.label and doc.label['en_US'], f'{op_id} missing en_US label'
        assert doc.risk in {'read', 'write', 'dangerous'}, f'{op_id} invalid risk: {doc.risk}'
        assert doc.exposure in {'none', 'assistant', 'all'}, f'{op_id} invalid exposure: {doc.exposure}'


def test_side_effect_risk_consistency(all_application_operations: list[Operation]):
    for op in all_application_operations:
        doc = get_operation_doc(op.operation_id, side_effect=op.side_effect)
        if op.side_effect:
            assert doc.risk in {'write', 'dangerous'}, f'{op.operation_id} has side_effect=True but risk is {doc.risk}'
        else:
            assert doc.risk == 'read', f'{op.operation_id} has side_effect=False but risk is {doc.risk}'


def test_restricted_exposure_operations(all_application_operations: list[Operation]):
    for op in all_application_operations:
        doc = get_operation_doc(op.operation_id, side_effect=op.side_effect)
        op_id = op.operation_id

        if op.streaming:
            assert doc.exposure == 'none', f"Streaming operation {op_id} must have exposure='none'"

        if (
            op_id.startswith('assistant.')
            or op_id.startswith('api_key.')
            or op_id.startswith('workspace.sandbox.')
            or op_id.startswith('workspace.member.')
            or op_id.startswith('workspace.invitation.')
            or op_id.startswith('provider.codex.')
            or op_id.startswith('artifact.publication.')
            or op_id == 'artifact.skill_resource.create'
        ):
            assert doc.exposure == 'none', f"Operation {op_id} must have exposure='none'"

        if op_id.startswith('pipeline.migration.'):
            assert doc.exposure == 'assistant', f"Operation {op_id} must have exposure='assistant'"

        if op_id in {'mcp.server.create', 'mcp.server.update'}:
            assert doc.exposure == 'assistant', f"Operation {op_id} must have exposure='assistant'"
            assert doc.risk == 'dangerous', f"Operation {op_id} must have risk='dangerous'"


def test_artifact_plugin_exposure_is_explicit(operations_by_id):
    from langbot.pkg.api.context import PrincipalType

    allowed = {'artifact.' + name for name in ('create', 'get', 'read', 'read_content', 'retain', 'release', 'delete')}
    for op_id, op in operations_by_id.items():
        if op_id.startswith('artifact.'):
            assert (PrincipalType.PLUGIN in op.principals) == (op_id in allowed)
            assert (get_operation_doc(op_id, side_effect=op.side_effect).exposure == 'all') == (op_id in allowed)


def test_principals_exposure_consistency(all_application_operations: list[Operation]):
    for op in all_application_operations:
        doc = get_operation_doc(op.operation_id, side_effect=op.side_effect)
        if op.principals is not None and PrincipalType.API_KEY not in op.principals:
            assert doc.exposure != 'all', (
                f"Operation {op.operation_id} without API_KEY principal cannot be exposure='all'"
            )


def test_domains_metadata(all_application_operations: list[Operation]):
    for op in all_application_operations:
        doc = get_operation_doc(op.operation_id, side_effect=op.side_effect)
        assert doc.domain in DOMAINS, f'Domain {doc.domain} of operation {op.operation_id} not in DOMAINS'

    for domain_name, meta in DOMAINS.items():
        assert 'label' in meta and 'zh_Hans' in meta['label'] and 'en_US' in meta['label']
        assert 'summary' in meta and meta['summary']


def test_published_catalog_incorporates_metadata(
    operations_by_id: dict[str, Operation], catalog_by_id: dict[str, dict]
):
    assert catalog_by_id.keys() == operations_by_id.keys()
    fields = ('domain', 'label', 'summary', 'description', 'risk', 'exposure')
    for op_id, data in catalog_by_id.items():
        op = operations_by_id[op_id]
        doc = get_operation_doc(op_id, side_effect=op.side_effect)
        assert {field: data[field] for field in fields} == {field: getattr(doc, field) for field in fields}, op_id


def test_parameter_descriptions_in_service_contracts(operations_by_id: dict[str, Operation]):
    # Verify parameter descriptions on service operations
    bot_get = operations_by_id['bot.get']
    schema = bot_get.input_type.model_json_schema()
    assert 'UUID of the bot' in schema['properties']['bot_uuid']['description']
    assert 'Whether to include secret values' in schema['properties']['include_secret']['description']

    pipeline_get = operations_by_id['pipeline.get']
    pipeline_schema = pipeline_get.input_type.model_json_schema()
    assert 'pipeline.list' in pipeline_schema['properties']['pipeline_uuid']['description']

    monitoring_errors = operations_by_id['monitoring.errors']
    mon_schema = monitoring_errors.input_type.model_json_schema()
    assert 'Maximum number of items' in mon_schema['properties']['limit']['description']
    assert 'Number of items to skip' in mon_schema['properties']['offset']['description']

    # Verify model_uuid maps to the corresponding list operation
    llm_get = operations_by_id['model.llm.get']
    assert 'model.llm.list' in llm_get.input_type.model_json_schema()['properties']['model_uuid']['description']

    emb_get = operations_by_id['model.embedding.get']
    assert 'model.embedding.list' in emb_get.input_type.model_json_schema()['properties']['model_uuid']['description']

    rerank_get = operations_by_id['model.rerank.get']
    assert 'model.rerank.list' in rerank_get.input_type.model_json_schema()['properties']['model_uuid']['description']

    # Verify server_uuid maps to mcp.server.list
    mcp_update = operations_by_id['mcp.server.update']
    assert 'mcp.server.list' in mcp_update.input_type.model_json_schema()['properties']['server_uuid']['description']

    mcp_delete = operations_by_id['mcp.server.delete']
    assert 'mcp.server.list' in mcp_delete.input_type.model_json_schema()['properties']['server_uuid']['description']

    # Verify pipeline.run and bot.routes.preview have parameter descriptions
    pipeline_run = operations_by_id['pipeline.run']
    run_schema = pipeline_run.input_type.model_json_schema()
    assert 'pipeline.list' in run_schema['properties']['pipeline_uuid']['description']

    route_preview = operations_by_id['bot.routes.preview']
    preview_schema = route_preview.input_type.model_json_schema()
    assert 'bot.list' in preview_schema['properties']['bot_uuid']['description']


def test_permission_management_operations_are_not_exposed(operations_by_id: dict[str, Operation]):
    for operation_id in ('plugin.permissions.get', 'plugin.permissions.update'):
        operation = operations_by_id[operation_id]
        assert get_operation_doc(operation_id, side_effect=operation.side_effect).exposure == 'none'


def test_referenced_operation_ids_exist(
    catalog_by_id: dict[str, dict],
):
    catalog_op_ids = catalog_by_id.keys()

    # 1. Parameter descriptions in input schema
    param_references: list[tuple[str, str]] = []
    for op_id, data in catalog_by_id.items():
        schema = data.get('input_schema', {})
        props = schema.get('properties', {})
        for prop_name, prop_def in props.items():
            desc = prop_def.get('description', '')
            if not desc:
                continue
            for match in re.findall(r'get it from\s+([a-zA-Z0-9_.]+)', desc, re.IGNORECASE):
                op_ref = match.rstrip('.,;: )')
                param_references.append((f'{op_id}.{prop_name}', op_ref))

    assert param_references, 'Expected parameter descriptions to contain operation references'
    for source, op_ref in param_references:
        assert op_ref in catalog_op_ids, f'Parameter {source} references non-existent operation {op_ref}'

    # 2. OperationDoc descriptions (Call <op_id> or get it from <op_id>)
    doc_references: list[tuple[str, str]] = []
    for op_id, doc in OPERATION_DOCS.items():
        desc = doc.description
        for match in re.findall(r'(?:Call|get it from)\s+([a-zA-Z0-9_.]+)', desc):
            op_ref = match.rstrip('.,;: )')
            if op_ref in {'statistics', 'events'}:
                continue
            doc_references.append((op_id, op_ref))

    assert doc_references, 'Expected OperationDoc descriptions to contain operation references'
    for source_op_id, op_ref in doc_references:
        assert op_ref in catalog_op_ids, (
            f'Operation {source_op_id} description references non-existent operation {op_ref}'
        )
