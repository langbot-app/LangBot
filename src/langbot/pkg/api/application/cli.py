"""Minimal command-line client for Pipeline Application API operations."""

from __future__ import annotations

import argparse
import json
import os

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


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not args.api_key:
        raise SystemExit('--api-key or LANGBOT_API_KEY is required')
    try:
        with ApplicationAPIClient(args.base_url, api_key=args.api_key) as client:
            if args.command == 'pipelines-list':
                result = client.list_pipelines()
            elif args.command == 'pipeline-get':
                result = client.get_pipeline(args.pipeline_uuid)
            elif args.command == 'pipeline-extensions-get':
                result = client.get_pipeline_extensions(args.pipeline_uuid)
            else:
                values = json.loads(args.json)
                if not isinstance(values, dict):
                    raise ValueError('--json must contain an object')
                client.update_pipeline_extensions(args.pipeline_uuid, **values)
                result = {'ok': True}
    except (ApplicationAPIClientError, ValueError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
