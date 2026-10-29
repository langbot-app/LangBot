"""Adapt application failures to existing in-process transport contracts."""

from contextvars import ContextVar

from .contracts import ApplicationAPIException


# HTTP already records the request's route, resource and before/after changes.
transport_records_audit = ContextVar('transport_records_application_audit', default=False)
application_audit_details = ContextVar('application_audit_details', default=None)


class ApplicationInputError(ValueError):
    """An invalid operation payload using the existing transport error contract."""

    status_code = 400


def raise_transport_error(exc: ApplicationAPIException):
    if exc.error.code == 'invalid_input':
        raise ApplicationInputError(exc.error.message) from exc
    if exc.error.code != 'invalid_output' and exc.__cause__ is not None:
        raise exc.__cause__ from None
    raise exc


async def invoke_application(ap, operation_id, context, payload):
    try:
        return await ap.application_api.execute(operation_id, context, payload)
    except ApplicationAPIException as exc:
        from .service_operations import MissingResourceResult

        if isinstance(exc.__cause__, MissingResourceResult):
            return None
        raise_transport_error(exc)


async def stream_application(ap, operation_id, context, payload):
    from contextlib import aclosing

    try:
        async with aclosing(ap.application_api.stream(operation_id, context, payload)) as frames:
            async for frame in frames:
                yield frame
    except ApplicationAPIException as exc:
        raise_transport_error(exc)
