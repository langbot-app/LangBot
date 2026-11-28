"""Same-origin browser approval; this endpoint never issues tokens."""

from html import escape

import quart

from .handoff import HarnessHandoffs


def register_handoff_route(app, ap):
    def page(message, *, ticket=None, label='', status=200):
        form = ''
        if ticket is not None:
            form = f'''<p>{escape(label)}</p><form method="post" action="/oauth/handoff">
            <input type="hidden" name="ticket" value="{escape(ticket)}">
            <label>Authenticator code <input name="code" inputmode="numeric" autocomplete="one-time-code"
                pattern="[0-9]{{6}}" maxlength="6" required></label>
            <button name="action" value="approve">Approve</button>
            <button name="action" value="cancel" formnovalidate>Cancel</button></form>'''
        response = quart.Response(
            f'<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" '
            f'content="width=device-width, initial-scale=1"><title>Harness approval</title>'
            f'<main><h1>Approve Harness sign-in</h1><p>{escape(message)}</p>{form}</main></html>',
            status=status, mimetype='text/html',
        )
        response.headers.update({
            'Cache-Control': 'no-store', 'Referrer-Policy': 'strict-origin',
            'X-Content-Type-Options': 'nosniff', 'X-Frame-Options': 'DENY',
            'Content-Security-Policy': "default-src 'none'; frame-ancestors 'none'; form-action 'self'; base-uri 'none'",
        })
        return response

    @app.route('/oauth/handoff', methods=['GET', 'POST'])
    async def browser_handoff():
        unavailable = 'This approval request is unavailable or has expired.'
        try:
            service = HarnessHandoffs(ap)
            if not quart.request.is_secure or f'https://{quart.request.host}' != service.base_url:
                return page(unavailable, status=404)
            if quart.request.method == 'GET':
                ticket = quart.request.args.get('ticket')
            else:
                if quart.request.headers.get('Origin') != service.base_url:
                    return page(unavailable, status=403)
                if quart.request.mimetype != 'application/x-www-form-urlencoded':
                    return page(unavailable, status=400)
                form = await quart.request.form
                ticket = form.get('ticket')
                action = form.get('action')
                code = form.get('code', '')
                if action == 'cancel':
                    if await service.decide(ticket) == 'cancelled':
                        return page('Approval cancelled. You can close this tab.')
                    return page(unavailable, status=404)
                if action != 'approve' or len(code) != 6 or not code.isascii() or not code.isdigit():
                    return page(unavailable, status=400)
                result = await service.decide(ticket, code=code)
                if result == 'approved':
                    return page('Approved. Return to Harness to finish binding your device.')
                if result != 'invalid':
                    return page(unavailable, status=404)
            label = await service.preview(ticket)
            if label is not None:
                message = ('Incorrect or already used code. Try again.' if quart.request.method == 'POST'
                           else 'Only approve a sign-in you started in Harness.')
                return page(message, ticket=ticket, label=label)
        except ValueError:
            pass
        return page(unavailable, status=404)
