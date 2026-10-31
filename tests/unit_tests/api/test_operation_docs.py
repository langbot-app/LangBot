"""Unit tests for ApplicationAPI operation documentation and exposure metadata."""

from __future__ import annotations

import pytest

from langbot.pkg.api.application.contracts import Operation
from langbot.pkg.api.application.operation_docs import DOMAINS, OPERATION_DOCS, OperationDoc, get_operation_doc
from langbot.pkg.api.application.service_operations import operations as service_operations
from langbot.pkg.api.application.auxiliary import operations as auxiliary_operations
from langbot.pkg.api.application.plugin_operations import operations as plugin_operations
from langbot.pkg.api.application.platform_setup import operations as platform_operations
from langbot.pkg.api.application.connection_operations import operations as connection_operations
from langbot.pkg.api.application.workspace_streams import operations as workspace_streams
from langbot.pkg.api.context import PrincipalType


@pytest.fixture(scope='module')
def all_application_operations() -> list[Operation]:
    return [
        *service_operations(),
        *auxiliary_operations(),
        *plugin_operations(),
        *platform_operations(),
        *connection_operations(),
        *workspace_streams(),
    ]


@pytest.fixture(scope='module')
def operations_by_id(all_application_operations: list[Operation]) -> dict[str, Operation]:
    return {op.operation_id: op for op in all_application_operations}


@pytest.fixture(scope='module')
def in_scope_operation_ids(operations_by_id: dict[str, Operation]) -> set[str]:
    in_scope = set()
    for op_id in operations_by_id:
        if op_id.startswith('monitoring.export.'):
            continue
        if (
            op_id.startswith('monitoring.')
            or op_id == 'stats.basic'
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
        ):
            in_scope.add(op_id)
    return in_scope


def test_in_scope_operations_coverage(in_scope_operation_ids: set[str], operations_by_id: dict[str, Operation]):
    assert len(in_scope_operation_ids) == 162
    assert len(OPERATION_DOCS) == 162

    # Check all in-scope operations are documented
    missing = in_scope_operation_ids - set(OPERATION_DOCS.keys())
    assert not missing, f'Missing documentation for operations: {missing}'

    # Check there are no extra operation IDs in OPERATION_DOCS
    extra = set(OPERATION_DOCS.keys()) - in_scope_operation_ids
    assert not extra, f'Extra undocumented or out-of-scope operation IDs in OPERATION_DOCS: {extra}'

    # Check all documented IDs actually exist in ApplicationAPI operations
    unknown = set(OPERATION_DOCS.keys()) - set(operations_by_id.keys())
    assert not unknown, f'Unknown operation IDs in OPERATION_DOCS: {unknown}'


def test_out_of_scope_operations_are_none(
    in_scope_operation_ids: set[str], all_application_operations: list[Operation]
):
    out_of_scope_ops = [op for op in all_application_operations if op.operation_id not in in_scope_operation_ids]
    assert len(out_of_scope_ops) == 72

    for op in out_of_scope_ops:
        doc = get_operation_doc(op.operation_id, side_effect=op.side_effect)
        assert doc.exposure == 'none', f"Out of scope operation {op.operation_id} must have exposure='none'"
        as_dict = op.as_dict()
        assert as_dict['exposure'] == 'none', (
            f"Out of scope operation {op.operation_id} as_dict must have exposure='none'"
        )


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
            or op_id.startswith('workspace.member.')
            or op_id.startswith('workspace.invitation.')
            or op_id.startswith('provider.codex.')
        ):
            assert doc.exposure == 'none', f"Operation {op_id} must have exposure='none'"

        if op_id.startswith('pipeline.migration.'):
            assert doc.exposure == 'assistant', f"Operation {op_id} must have exposure='assistant'"


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


def test_as_dict_incorporates_metadata(all_application_operations: list[Operation]):
    for op in all_application_operations:
        data = op.as_dict()
        assert 'domain' in data
        assert 'label' in data
        assert 'summary' in data
        assert 'description' in data
        assert 'risk' in data
        assert 'exposure' in data

        doc = get_operation_doc(op.operation_id, side_effect=op.side_effect)
        assert data['domain'] == doc.domain
        assert data['label'] == doc.label
        assert data['summary'] == doc.summary
        assert data['description'] == doc.description
        assert data['risk'] == doc.risk
        assert data['exposure'] == doc.exposure


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
