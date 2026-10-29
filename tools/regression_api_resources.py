"""Local Skill publications and disabled MCP configuration HTTP contracts."""

from contextlib import contextmanager

from regression_api_checks import check, request, unique_name, user_headers
from regression_local_cases import api, require
from regression_resource_cases import cleanup, journal


@contextmanager
def _named_resource(suite, row, collection, body, item_key, ownership_field, headers):
    name = body['name']
    path = collection + '/' + name
    request(suite, row, 'GET', path, expected=404, headers=headers)
    owned = {'kind': item_key, 'name': name, 'state': 'creating'}
    row.setdefault('owned_resources', []).append(owned)
    journal(suite, row)

    def remove():
        status, response = api(suite, 'GET', path, headers=headers)
        if status != 404:
            require(status == 200 and response.get('code') == 0, 'Cannot read owned resource before cleanup')
            item = response['data'][item_key]
            require(
                item.get('name') == name and item.get(ownership_field) == body[ownership_field],
                'Named resource ownership changed before cleanup',
            )
            if 'uuid' in owned:
                require(item.get('uuid') == owned['uuid'], 'Named resource identity changed before cleanup')
            request(suite, row, 'DELETE', path, headers=headers)
        request(suite, row, 'GET', path, expected=404, headers=headers)
        owned['state'] = 'deleted'

    try:
        created = request(suite, row, 'POST', collection, body, headers=headers)
        owned['state'] = 'created'
        if created.get('uuid'):
            owned['uuid'] = created['uuid']
        journal(suite, row)
        yield path, created
    finally:
        cleanup(suite, row, 'cleanup_' + item_key, remove)


def _expect_rejection(suite, row, method, path, body, *, expected, headers, verify):
    try:
        request(suite, row, method, path, body, expected=expected, headers=headers)
    except Exception:
        try:
            verify()
        except Exception:
            # Both assertions are recorded; retain the original HTTP failure.
            pass
        raise
    verify()


def skills_case(suite, row):
    headers = user_headers(suite)
    name = unique_name()
    instructions = '# API fixture\n\nRead the local reference file.'
    body = {
        'name': name,
        'display_name': 'API contract fixture',
        'description': 'Owned Skill fixture ' + name,
        'instructions': instructions,
    }
    with _named_resource(suite, row, '/api/v1/skills', body, 'skill', 'description', headers) as (path, created):
        skill = created['skill']
        initial_revision = skill.get('revision')
        check(
            row,
            'skill_created',
            skill.get('name') == name and bool(initial_revision),
            'Skill identity/revision missing',
        )
        readback = request(suite, row, 'GET', path, headers=headers)['skill']
        check(row, 'skill_readback', readback == skill, 'Created Skill differs from its readback')
        listed = request(suite, row, 'GET', '/api/v1/skills', headers=headers)['skills']
        check(row, 'skill_listed', sum(item.get('name') == name for item in listed) == 1, 'Skill listing is not unique')
        preview = request(suite, row, 'GET', path + '/preview', headers=headers)
        check(row, 'skill_preview', preview.get('instructions') == instructions, 'Skill preview lost instructions')

        file_path = path + '/files/references/fixture.txt'
        content = 'Skill API fixture: 中文\n' + name + '\n'
        written = request(
            suite, row, 'PUT', file_path, {'content': content, 'base_revision': initial_revision}, headers=headers
        )
        file_revision = written.get('revision')
        check(
            row,
            'skill_file_published',
            bool(file_revision)
            and file_revision != initial_revision
            and written.get('bytes_written') == len(content.encode()),
            'Skill file write did not publish the expected UTF-8 bytes as a new revision',
        )
        file_readback = request(suite, row, 'GET', file_path, headers=headers)
        check(
            row,
            'skill_file_readback',
            file_readback.get('content') == content
            and file_readback.get('path') == 'references/fixture.txt'
            and file_readback.get('skill', {}).get('name') == name,
            'Skill file readback differs from the written content or identity',
        )
        files = request(suite, row, 'GET', path + '/files?path=references', headers=headers)
        check(
            row,
            'skill_files_listed',
            any(
                item.get('path') == 'references/fixture.txt'
                and item.get('size') == len(content.encode())
                and item.get('is_dir') is False
                for item in files.get('entries', [])
            ),
            'Written Skill file is missing from the directory listing',
        )

        updated_instructions = '# Updated API fixture\n\nKeep the local reference file.'
        updated = request(
            suite,
            row,
            'PUT',
            path,
            {'instructions': updated_instructions, 'base_revision': file_revision},
            headers=headers,
        )['skill']
        check(
            row,
            'skill_updated',
            updated.get('instructions') == updated_instructions and updated.get('revision') != file_revision,
            'Skill update did not publish changed instructions',
        )
        preview = request(suite, row, 'GET', path + '/preview', headers=headers)
        check(
            row, 'skill_updated_preview', preview.get('instructions') == updated_instructions, 'Skill preview is stale'
        )
        unchanged = request(
            suite,
            row,
            'PUT',
            path,
            {'instructions': updated_instructions, 'base_revision': updated['revision']},
            headers=headers,
        )['skill']
        check(
            row,
            'skill_update_idempotent',
            unchanged.get('revision') == updated['revision'],
            'No-op Skill update changed content revision',
        )
        before_conflict = request(suite, row, 'GET', path, headers=headers)['skill']

        def verify_stale_update():
            after_conflict = request(suite, row, 'GET', path, headers=headers)['skill']
            check(
                row,
                'skill_stale_update_preserved',
                after_conflict == before_conflict,
                'Rejected Skill update changed the published state',
            )

        _expect_rejection(
            suite,
            row,
            'PUT',
            path,
            {'instructions': 'stale metadata must not win', 'base_revision': initial_revision},
            expected=409,
            headers=headers,
            verify=verify_stale_update,
        )
        before_file_conflict = request(suite, row, 'GET', file_path, headers=headers)
        before_file_skill = request(suite, row, 'GET', path, headers=headers)['skill']

        def verify_stale_file():
            after_file_conflict = request(suite, row, 'GET', file_path, headers=headers)
            after_conflict = request(suite, row, 'GET', path, headers=headers)['skill']
            check(
                row,
                'skill_stale_file_preserved',
                after_file_conflict == before_file_conflict and after_conflict == before_file_skill,
                'Rejected Skill file write changed the file or published revision',
            )

        # The file route currently maps revision conflicts to HTTP 400.
        _expect_rejection(
            suite,
            row,
            'PUT',
            file_path,
            {'content': 'stale file must not win', 'base_revision': file_revision},
            expected=400,
            headers=headers,
            verify=verify_stale_file,
        )
        request(suite, row, 'DELETE', path, headers=headers)
        request(suite, row, 'GET', path, expected=404, headers=headers)
        request(suite, row, 'DELETE', path, expected=400, headers=headers)
        request(suite, row, 'GET', path, expected=404, headers=headers)
        check(
            row,
            'skill_deleted',
            not any(
                item.get('name') == name
                for item in request(suite, row, 'GET', '/api/v1/skills', headers=headers)['skills']
            ),
            'Deleted Skill remains listed',
        )
        return {'skill_name': name, 'revision': before_conflict['revision']}


def _mcp_config(server):
    return {
        key: server.get(key) for key in ('uuid', 'workspace_uuid', 'name', 'enable', 'mode', 'extra_args', 'readme')
    }


def mcp_case(suite, row):
    headers = user_headers(suite)
    name = unique_name()
    collection = '/api/v1/mcp/servers'
    body = {
        'name': name,
        'enable': False,
        'mode': 'remote',
        'extra_args': {'url': 'http://127.0.0.1:9/mcp'},
        'readme': 'Owned disabled MCP fixture ' + name,
    }
    with _named_resource(suite, row, collection, body, 'server', 'readme', headers) as (path, created):
        server = request(suite, row, 'GET', path, headers=headers)['server']
        check(
            row,
            'mcp_created_disabled',
            bool(created.get('uuid'))
            and server.get('uuid') == created['uuid']
            and server.get('workspace_uuid') == suite.variables['workspace_uuid']
            and all(server.get(key) == value for key, value in body.items()),
            'MCP create/readback changed identity, disabled state or configuration',
        )
        servers = request(suite, row, 'GET', collection, headers=headers)['servers']
        check(
            row,
            'mcp_listed',
            sum(item.get('name') == name and item.get('uuid') == created['uuid'] for item in servers) == 1,
            'MCP listing did not return the created server exactly once',
        )
        update = {'enable': False, 'extra_args': {'url': 'http://127.0.0.1:9/updated-mcp'}}
        request(suite, row, 'PUT', path, update, headers=headers)
        updated = request(suite, row, 'GET', path, headers=headers)['server']
        check(
            row,
            'mcp_updated_disabled',
            _mcp_config(updated) == {**_mcp_config(server), **update},
            'MCP update changed unrelated configuration or enabled the server',
        )
        request(suite, row, 'PUT', path, update, headers=headers)
        repeated = request(suite, row, 'GET', path, headers=headers)['server']
        check(
            row,
            'mcp_update_idempotent',
            _mcp_config(repeated) == _mcp_config(updated),
            'Repeated MCP update changed configuration',
        )

        def verify_duplicate():
            after_duplicate = request(suite, row, 'GET', path, headers=headers)['server']
            servers = request(suite, row, 'GET', collection, headers=headers)['servers']
            check(
                row,
                'mcp_duplicate_preserved',
                _mcp_config(after_duplicate) == _mcp_config(updated)
                and sum(item.get('name') == name for item in servers) == 1,
                'Duplicate MCP create changed the original or added another server',
            )

        _expect_rejection(suite, row, 'POST', collection, body, expected=400, headers=headers, verify=verify_duplicate)

        def verify_invalid_transport():
            after_invalid = request(suite, row, 'GET', path, headers=headers)['server']
            row['mcp_transport'] = {'before': updated['mode'], 'after': after_invalid['mode']}
            check(
                row,
                'mcp_invalid_transport_preserved',
                _mcp_config(after_invalid) == _mcp_config(updated),
                'Invalid MCP transport changed stored configuration',
            )

        _expect_rejection(
            suite,
            row,
            'PUT',
            path,
            {'mode': 'qa-invalid-transport', 'enable': False},
            expected=400,
            headers=headers,
            verify=verify_invalid_transport,
        )
        request(suite, row, 'DELETE', path, headers=headers)
        request(suite, row, 'GET', path, expected=404, headers=headers)
        request(suite, row, 'DELETE', path, expected=404, headers=headers)
        servers = request(suite, row, 'GET', collection, headers=headers)['servers']
        check(
            row,
            'mcp_deleted',
            not any(item.get('name') == name for item in servers),
            'Deleted MCP server remains listed',
        )
        return {'mcp_name': name, 'uuid': created['uuid']}
