from langbot.pkg.api.context import ExecutionContext, RequestContext
from langbot.pkg.api.http.context import ExecutionContext as HTTPExecutionContext
from langbot.pkg.api.http.context import RequestContext as HTTPRequestContext


def test_application_context_types_are_http_independent_and_compatibly_reexported():
    assert RequestContext is HTTPRequestContext
    assert ExecutionContext is HTTPExecutionContext
    assert RequestContext.__module__ == 'langbot.pkg.api.context'
