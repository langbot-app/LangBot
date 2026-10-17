"""Minimal command-line client for Pipeline Application API operations."""

from __future__ import annotations

import argparse
import dataclasses
import json
import os

from .api import ApplicationAPI, ApplicationAPIException, PipelineExtensionsUpdateInput
from .client import ApplicationAPIClient, ApplicationAPIClientError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='langbot-api')
    parser.add_argument('--base-url', default=os.getenv('LANGBOT_URL', 'http://127.0.0.1:5300'))
    parser.add_argument('--api-key', default=os.getenv('LANGBOT_API_KEY'))
    subparsers = parser.add_subparsers(dest='command', required=True)

    subparsers.add_parser('pipelines-list')
    get_parser = subparsers.add_parser('pipeline-get')
    get_parser.add_argument('pipeline_uuid')
    extensions_parser = subparsers.add_parser('pipeline-extensions-get')
    extensions_parser.add_argument('pipeline_uuid')
    update_parser = subparsers.add_parser('pipeline-extensions-update')
    update_parser.add_argument('pipeline_uuid')
    update_parser.add_argument('--json', required=True, help='Complete extension replacement object')
    return parser


def _parse_extension_values(raw: str, pipeline_uuid: str) -> dict:
    """Parse and strictly validate one complete extension replacement object."""

    try:
        values = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f'--json must be valid JSON: {exc.msg}') from exc
    if not isinstance(values, dict):
        raise ValueError('--json must contain an object')
    known_fields = {field.name for field in dataclasses.fields(PipelineExtensionsUpdateInput)} - {'pipeline_uuid'}
    unknown_fields = sorted(set(values) - known_fields)
    if unknown_fields:
        raise ValueError(f'--json contains unsupported fields: {", ".join(unknown_fields)}')
    if 'bound_plugins' not in values:
        raise ValueError('--json must include bound_plugins')
    try:
        input = PipelineExtensionsUpdateInput(pipeline_uuid=pipeline_uuid, **values)
    except TypeError as exc:
        raise ValueError(str(exc)) from exc
    try:
        ApplicationAPI._validate_input(input, PipelineExtensionsUpdateInput)
    except ApplicationAPIException as exc:
        raise ValueError(exc.error.message) from exc
    return values


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
    except SystemExit as exc:
        # Keep this command machine-readable even for malformed invocations.
        # argparse still emits its normal usage text to stderr, while callers
        # can rely on one stable JSON error object on stdout.
        code = exc.code if isinstance(exc.code, int) else 2
        print(json.dumps({'error': {'code': 'invalid_arguments', 'message': 'Invalid command-line arguments'}}))
        return code or 0
    values = None
    if args.command == 'pipeline-extensions-update':
        try:
            values = _parse_extension_values(args.json, args.pipeline_uuid)
        except ValueError as exc:
            print(
                json.dumps(
                    {'error': {'code': 'invalid_input', 'message': str(exc)}},
                    ensure_ascii=False,
                )
            )
            return 1
    if not args.api_key:
        print(
            json.dumps(
                {
                    'error': {
                        'code': 'missing_api_key',
                        'message': '--api-key or LANGBOT_API_KEY is required',
                    }
                }
            )
        )
        return 2
    try:
        with ApplicationAPIClient(args.base_url, api_key=args.api_key) as client:
            if args.command == 'pipelines-list':
                result = client.list_pipelines()
            elif args.command == 'pipeline-get':
                result = client.get_pipeline(args.pipeline_uuid)
            elif args.command == 'pipeline-extensions-get':
                result = client.get_pipeline_extensions(args.pipeline_uuid)
            else:
                assert values is not None
                client.update_pipeline_extensions(args.pipeline_uuid, **values)
                result = {'ok': True}
    except (ApplicationAPIClientError, ValueError, TypeError) as exc:
        code = getattr(exc, 'code', None) or 'invalid_input'
        print(
            json.dumps(
                {'error': {'code': code, 'message': str(exc)}},
                ensure_ascii=False,
            )
        )
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
