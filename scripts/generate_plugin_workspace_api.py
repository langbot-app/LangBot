"""Generate SDK workspace domains from the Core catalog without starting services.

Run with Core's Python environment. The SDK output has no Core dependency.
Use --check to detect catalog drift without modifying the output.
"""

from __future__ import annotations

import argparse
import keyword
from pathlib import Path
import re
import sys


DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / 'sdk/src/langbot_plugin/api/proxies/workspace_domains.py'


def identifier(value: str) -> str:
    name = re.sub(r'\W', '_', value)
    if not name or name[0].isdigit():
        name = '_' + name
    if keyword.iskeyword(name) or name in {'self', '_workspace', '_timeout'}:
        name += '_'
    return name


def type_name(value: str) -> str:
    return ''.join(part.capitalize() for part in re.findall(r'[A-Za-z0-9]+', value))


def plugin_catalog() -> list[dict]:
    from langbot.pkg.api.application.api import ApplicationAPI

    return eligible_operations(ApplicationAPI(None).operation_catalog())


def eligible_operations(catalog: list[dict]) -> list[dict]:
    return sorted(
        (
            operation
            for operation in catalog
            if operation['exposure'] == 'all'
            and not operation['streaming']
            and (operation['principals'] is None or 'plugin' in operation['principals'])
        ),
        key=lambda operation: operation['id'],
    )


class SchemaTypes:
    def __init__(self):
        self.definitions: list[str] = []
        self.names: set[str] = set()

    def annotation(self, schema: dict, name: str, root: dict) -> str:
        if '$ref' in schema:
            reference = schema['$ref']
            if not reference.startswith('#/'):
                raise ValueError(f'Unsupported schema reference: {reference}')
            target = root
            for part in reference[2:].split('/'):
                target = target[part.replace('~1', '/').replace('~0', '~')]
            return self.annotation(target, name + type_name(reference.split('/')[-1]), root)
        for union in ('anyOf', 'oneOf'):
            if union in schema:
                return (
                    'Union['
                    + ', '.join(
                        self.annotation(item, f'{name}Variant{index}', root) for index, item in enumerate(schema[union])
                    )
                    + ']'
                )
        if 'const' in schema or 'enum' in schema:
            values = schema.get('enum', [schema.get('const')])
            return 'Literal[' + ', '.join(repr(value) for value in values) + ']'
        kind = schema.get('type')
        if kind == 'object':
            properties = schema.get('properties', {})
            if properties:
                if name in self.names:
                    return name
                self.names.add(name)
                required = schema.get('required', [])
                fields = []
                for field, value in sorted(properties.items()):
                    annotation = self.annotation(value, name + type_name(field), root)
                    if field not in required:
                        annotation = f'NotRequired[{annotation}]'
                    fields.append(f'    {field!r}: {annotation},')
                self.definitions.append(f'{name} = TypedDict({name!r}, {{\n' + '\n'.join(fields) + '\n})')
                return name
            additional = schema.get('additionalProperties', {})
            value = self.annotation(additional, name + 'Value', root) if isinstance(additional, dict) else 'JSONValue'
            return f'dict[str, {value}]'
        if kind == 'array':
            if 'prefixItems' in schema:
                items = (
                    'Union['
                    + ', '.join(
                        self.annotation(item, f'{name}Item{index}', root)
                        for index, item in enumerate(schema['prefixItems'])
                    )
                    + ']'
                )
            else:
                items = self.annotation(schema.get('items', {}), name + 'Item', root)
            return f'builtins.list[{items}]'
        if kind in {'string', 'integer', 'number', 'boolean', 'null'}:
            return {'string': 'str', 'integer': 'int', 'number': 'float', 'boolean': 'bool', 'null': 'None'}[kind]
        if not schema or set(schema) <= {'title', 'description', 'default'}:
            return 'JSONValue'
        raise ValueError(f'Unsupported schema for {name}: {schema}')


HEADER = '''"""Typed Workspace Application API domains.

Regenerate with LangBot/scripts/generate_plugin_workspace_api.py; requires Core
only at generation time. Calls preserve workspace.call()'s ok/result/error envelope
and authorization. No run_id is required to construct or use these domains.
Python keywords gain a trailing underscore (e.g. import_); non-identifier
characters become underscores. Parameter aliases are documented on each method
and always forwarded using the original schema keys.
An omitted optional field without a schema default is not sent. Open JSON objects
use JSONValue; declared object properties use TypedDict. JSON arrays, including
fixed-length arrays, remain lists on the wire.
"""

import builtins
from typing import TYPE_CHECKING, Generic, Literal, TypeVar, Union, cast

from typing_extensions import NotRequired, TypedDict

if TYPE_CHECKING:
    from .workspace import WorkspaceOperationsProxy

JSONValue = Union[None, bool, int, float, str, list["JSONValue"], dict[str, "JSONValue"]]
Result = TypeVar("Result")


class OperationError(TypedDict):
    code: str
    message: str
    details: NotRequired[JSONValue]


class OperationSuccess(TypedDict, Generic[Result]):
    ok: Literal[True]
    result: Result
    operation: NotRequired[dict[str, JSONValue]]


class OperationFailure(TypedDict):
    ok: Literal[False]
    error: OperationError
    operation: NotRequired[dict[str, JSONValue]]


OperationResult = Union[OperationSuccess[Result], OperationFailure]


class _Unset:
    pass


_UNSET = _Unset()
'''


def render(catalog: list[dict]) -> str:
    operations = eligible_operations(catalog)
    schemas = SchemaTypes()
    domains: dict[tuple[str, ...], dict] = {(): {}}
    for operation in operations:
        parts = tuple(operation['id'].split('.'))
        for depth in range(len(parts) - 1):
            domains.setdefault(parts[:depth], {})[parts[depth]] = parts[: depth + 1]
            domains.setdefault(parts[: depth + 1], {})
        domains[parts[:-1]][parts[-1]] = operation
    classes = []
    for path, members in sorted(domains.items(), key=lambda item: (-len(item[0]), item[0])):
        class_name = type_name('.'.join(path)) + 'Domain' if path else 'WorkspaceDomains'
        lines = [
            f'class {class_name}:',
            '    def __init__(self, workspace: "WorkspaceOperationsProxy"):',
            '        self._workspace = workspace',
        ]
        aliases = [identifier(member) for member in members]
        if len(set(aliases)) != len(aliases):
            raise ValueError(f'Conflicting Python member names in {path}')
        for member, value in sorted(members.items()):
            alias = identifier(member)
            if isinstance(value, tuple):
                child = type_name('.'.join(value)) + 'Domain'
                lines.append(f'        self.{alias} = {child}(workspace)')
        for member, operation in sorted(members.items()):
            if isinstance(operation, tuple):
                continue
            operation_id = operation['id']
            prefix = type_name(operation_id)
            input_schema = operation['input_schema']
            input_type = schemas.annotation(input_schema, prefix + 'Arguments', input_schema)
            parameters = []
            arguments = []
            omissions = []
            aliases = []
            for field, schema in sorted(input_schema.get('properties', {}).items()):
                alias = identifier(field)
                annotation = schemas.annotation(schema, prefix + type_name(field) + 'Input', input_schema)
                default = ''
                if field not in input_schema.get('required', []):
                    if 'default' in schema:
                        default = f' = {schema["default"]!r}'
                    else:
                        annotation = f'Union[{annotation}, _Unset]'
                        default = ' = _UNSET'
                        omissions.append(alias)
                parameters.append(f'{alias}: {annotation}{default}')
                if alias not in omissions:
                    arguments.append(f'{field!r}: {alias}')
                aliases.append(f'{alias} -> {field}')
            if len(set(identifier(field) for field in input_schema.get('properties', {}))) != len(parameters):
                raise ValueError(f'Conflicting Python parameters in {operation_id}')
            output = schemas.annotation(operation['output_schema'], prefix + 'Output', operation['output_schema'])
            signature = ', *, ' + ', '.join(parameters) if parameters else ''
            lines.extend(['', f'    async def {identifier(member)}(self{signature}) -> OperationResult[{output}]:'])
            doc = operation_id + ': ' + operation.get('description', operation.get('summary', ''))
            if aliases:
                doc += '\nParameters (Python -> wire): ' + ', '.join(aliases) + '.'
            lines.append(f'        {doc!r}')
            if parameters:
                lines.append(f'        arguments: {input_type} = {{' + ', '.join(arguments) + '}')
                for field in sorted(input_schema.get('properties', {})):
                    alias = identifier(field)
                    if alias in omissions:
                        lines.append(f'        if not isinstance({alias}, _Unset):')
                        lines.append(f'            arguments[{field!r}] = {alias}')
            forwarding = ', **arguments' if parameters else ''
            lines.append(
                f'        return cast(OperationResult[{output}], await self._workspace.call({operation_id!r}{forwarding}))'
            )
        classes.append('\n'.join(lines))
    return HEADER + '\n\n' + '\n\n'.join(schemas.definitions + classes) + '\n'


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    text = render(plugin_catalog())
    if args.check:
        if not args.output.exists() or args.output.read_text(encoding='utf-8') != text:
            print('Workspace domains are out of date; run the generator.', file=sys.stderr)
            return 1
        return 0
    args.output.write_text(text, encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
