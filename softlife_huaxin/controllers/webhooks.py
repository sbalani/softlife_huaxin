"""Inbound webhook receiver for Huaxin cloud callbacks.

Huaxin POSTs two kinds of payload to our notify_url:
  * order events   -> { responType: "order", data: {...} }
  * device faults  -> { deviceId, subject, htmlBody }
We disambiguate by shape, persist, and ACK with {"result": true, "message": "OK"}.
"""
import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class HuaxinWebhookController(http.Controller):

    @http.route('/huaxin/notify', type='http', auth='none', methods=['POST'], csrf=False)
    def notify(self, **kwargs):
        icp = request.env['ir.config_parameter'].sudo()

        # Optional shared-secret check (?token= or X-Huaxin-Token header).
        token = icp.get_param('softlife.huaxin.notify_token')
        if token:
            provided = (
                request.httprequest.args.get('token')
                or request.httprequest.headers.get('X-Huaxin-Token', '')
            )
            if provided != token:
                return self._json({'result': False, 'message': 'invalid token'}, status=403)

        body = self._read_json_body()

        client = request.env['softlife.huaxin.client'].sudo()
        try:
            if body.get('responType') == 'order':
                client.handle_order_webhook(body)
            elif 'subject' in body and 'deviceId' in body:
                client.handle_fault_webhook(body)
            else:
                _logger.info('Huaxin notify: unrecognised payload: %s', body)
        except Exception as exc:  # never let Huaxin see a 500 — they would retry forever
            _logger.exception('Huaxin webhook handling failed: %s', exc)

        return self._json({'result': True, 'message': 'OK'})

    @staticmethod
    def _read_json_body():
        try:
            data = request.get_json_data()
            if data:
                return data
        except Exception:
            pass
        # Fallback: form-encoded body.
        form = dict(request.httprequest.form or {})
        if form:
            return form
        raw = request.httprequest.get_data()
        try:
            return json.loads(raw.decode('utf-8')) if raw else {}
        except Exception:
            return {}

    @staticmethod
    def _json(payload, status=200):
        return request.make_response(
            json.dumps(payload),
            headers=[('Content-Type', 'application/json')],
            status=status,
        )
