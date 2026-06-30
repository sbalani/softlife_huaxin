"""The Huaxin bridge client.

A single TransientModel that knows how to talk to the Huaxin cloud: authorize,
send the fixed credential block, and receive webhook payloads. Every other
module asks this client in plain terms and never deals with Huaxin's protocol.

Credential model: Huaxin issues a FIXED block (mch_id, mch_secret, nonce_str,
time_Stamp, sign). We send it verbatim on every call. There is NO per-request
signature computation (the published MD5 scheme is not used for this account).

Stub mode: when credentials are missing, outbound calls return canned data so
the system is demoable before the keys are entered.
"""
import datetime
import json
import logging
import time

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

AUTH_TTL_SECONDS = 15 * 60  # re-authorize after 15 minutes


class SoftlifeHuaxinClient(models.TransientModel):
    _name = 'softlife.huaxin.client'
    _description = 'Huaxin Cloud Client (bridge)'

    # ------------------------------------------------------------------
    # Config helpers
    # ------------------------------------------------------------------
    @api.model
    def _param(self, key, default=False):
        return self.env['ir.config_parameter'].sudo().get_param(key, default)

    @api.model
    def _is_stub(self):
        return not (
            self._param('softlife.huaxin.base_url')
            and self._param('softlife.huaxin.mch_id')
            and self._param('softlife.huaxin.mch_secret')
            and self._param('softlife.huaxin.sign')
        )

    @api.model
    def _verify_ssl(self):
        return self._param('softlife.huaxin.verify_ssl', 'True') not in ('False', 'false', '0')

    @api.model
    def _common_params(self):
        """The fixed credential block Huaxin issues. Sent verbatim — never recomputed."""
        return {
            'mch_id': self._param('softlife.huaxin.mch_id') or '',
            'mch_secret': self._param('softlife.huaxin.mch_secret') or '',
            'nonce_str': self._param('softlife.huaxin.nonce_str') or '',
            'time_Stamp': self._param('softlife.huaxin.time_stamp') or '',
            'create_ip': self._param('softlife.huaxin.create_ip', '127.0.0.1') or '127.0.0.1',
            'notify_url': self._param('softlife.huaxin.notify_url', '') or '',
            'sign': self._param('softlife.huaxin.sign') or '',
        }

    # ------------------------------------------------------------------
    # Session
    # ------------------------------------------------------------------
    @api.model
    def _get_session(self):
        icp = self.env['ir.config_parameter'].sudo()
        auth = icp.get_param('softlife.huaxin.authorization')
        jsid = icp.get_param('softlife.huaxin.jsession_id')
        auth_at = icp.get_param('softlife.huaxin.auth_at')
        if auth and jsid and auth_at and (time.time() - float(auth_at)) < AUTH_TTL_SECONDS:
            return auth, jsid
        return self._authorize()

    @api.model
    def _authorize(self):
        if self._is_stub():
            return 'stub-authorization', 'stub-jsession'
        import requests
        base = self._param('softlife.huaxin.base_url').rstrip('/')
        body = self._common_params()  # already includes the static 'sign'
        r = requests.post(f'{base}/machine/cloud/api/authorize', json=body, timeout=30,
                          verify=self._verify_ssl())
        data = r.json()
        if str(data.get('code')) != '200':
            raise UserError(_('Huaxin authorize failed: %s') % data.get('msg'))
        auth = (data.get('data') or {}).get('authorization')
        jsid = data.get('jsessionId')
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('softlife.huaxin.authorization', auth)
        icp.set_param('softlife.huaxin.jsession_id', jsid)
        icp.set_param('softlife.huaxin.auth_at', str(time.time()))
        return auth, jsid

    # ------------------------------------------------------------------
    # Generic call
    # ------------------------------------------------------------------
    @api.model
    def _call(self, path, extra=None):
        if self._is_stub():
            return self._stub_response(path, extra)
        import requests
        auth, jsid = self._get_session()
        base = self._param('softlife.huaxin.base_url').rstrip('/')
        body = self._common_params()  # already includes the static 'sign'
        if extra:
            body.update(extra)
        headers = {
            'Authorization': auth,
            'Cookie': f'JSESSIONID={jsid};SESSION={jsid}',
            'jsessionId': jsid,
        }
        r = requests.post(f'{base}{path}', json=body, headers=headers, timeout=60,
                          verify=self._verify_ssl())
        data = r.json()
        # Surface sign/credential rejections clearly — they mean the configured block is wrong.
        if str(data.get('code')) == '208' and 'sign' in (data.get('msg') or '').lower():
            raise UserError(_(
                'Huaxin rejected the request (%s). Check the Sign value and the credential block in Settings.',
            ) % data.get('msg'))
        # Auto re-auth once on auth-related failure.
        if str(data.get('code')) == '208' and 'auth' in (data.get('msg') or '').lower():
            self._authorize()
            return self._call(path, extra)
        return data

    # ------------------------------------------------------------------
    # High-level operations
    # ------------------------------------------------------------------
    @api.model
    def _device_rows(self, data):
        payload = data.get('data')
        if isinstance(payload, dict):
            return payload.get('list') or payload.get('devices') or []
        if isinstance(payload, list):
            return payload
        return []

    @api.model
    def sync_devices(self):
        """Upsert softlife.machine from Huaxin /devices (matched by device_imei)."""
        data = self._call('/machine/cloud/api/devices')
        rows = self._device_rows(data)
        machine_model = self.env['softlife.machine']
        count = 0
        for row in rows:
            imei = row.get('deviceImei')
            if not imei:
                continue
            vals = {
                'device_imei': imei,
                'device_id_huaxin': row.get('deviceId'),
                'name': row.get('deviceName') or imei,
            }
            machine = machine_model.search([('device_imei', '=', imei)], limit=1)
            if machine:
                machine.write(vals)
                machine.write({'huaxin_last_sync': fields.Datetime.now()})
            else:
                # New Huaxin device not yet assigned to a customer — create unassigned.
                machine = machine_model.create(vals)
                machine.write({'huaxin_last_sync': fields.Datetime.now()})
            count += 1
        _logger.info('Huaxin sync_devices: %s machine(s) updated/created', count)
        return count

    @api.model
    def pull_temperatures(self, machine, began=None, end=None):
        extra = {
            'device_imei': machine.device_imei,
            'began_time': began or '',
            'end_time': end or '',
        }
        data = self._call('/machine/cloud/api/device/temperatures/trackings', extra)
        payload = data.get('data') or {}
        category = payload.get('category') or []
        temp_model = self.env['softlife.huaxin.temperature']
        created = 0
        for series in payload.get('dataset') or []:
            sname = series.get('seriesname') or 'temperature'
            for i, point in enumerate(series.get('data') or []):
                ts = category[i] if i < len(category) else None
                temp_model.create({
                    'machine_id': machine.id,
                    'reading_time': self._parse_time(ts) or fields.Datetime.now(),
                    'series_name': sname,
                    'value': float(point.get('value') or 0.0),
                    'raw': json.dumps(point),
                })
                created += 1
        if created:
            machine.write({'huaxin_last_sync': fields.Datetime.now()})
        return created

    # ------------------------------------------------------------------
    # Inbound webhooks
    # ------------------------------------------------------------------
    @api.model
    def handle_order_webhook(self, body):
        data = body.get('data') or {}
        imei = data.get('deviceImei')
        machine = self.env['softlife.machine'].search([('device_imei', '=', imei)], limit=1)
        self.env['softlife.huaxin.order'].create({
            'machine_id': machine.id if machine else False,
            'device_imei': imei or '',
            'order_code': data.get('orderCode') or '',
            'out_trade_no': data.get('outTradeNo') or '',
            'order_state': (data.get('orderState') or '').upper(),
            'order_time': self._parse_time(data.get('orderTime')) or fields.Datetime.now(),
            'price': float(data.get('price') or 0.0),
            'amount': float(data.get('amount') or 0.0),
            'product_name': data.get('productName') or '',
            'detail_raw': data.get('detail') or '',
            'raw': json.dumps(body, default=str),
        })
        _logger.info('Huaxin order webhook stored: %s', data.get('orderCode'))

    @api.model
    def handle_fault_webhook(self, body):
        device_id = body.get('deviceId')
        machine = (
            self.env['softlife.machine'].search([('device_id_huaxin', '=', device_id)], limit=1)
            or self.env['softlife.machine'].search([('device_imei', '=', device_id)], limit=1)
        )
        self.env['softlife.huaxin.fault'].create({
            'machine_id': machine.id if machine else False,
            'device_id_huaxin': device_id or '',
            'subject': body.get('subject') or '',
            'html_body': body.get('htmlBody') or '',
            'received_at': fields.Datetime.now(),
            'raw': json.dumps(body, default=str),
        })
        _logger.info('Huaxin fault webhook stored for device %s: %s', device_id, body.get('subject'))

    # ------------------------------------------------------------------
    # Crons
    # ------------------------------------------------------------------
    @api.model
    def _cron_sync_devices(self):
        try:
            self.sync_devices()
        except Exception as e:
            _logger.warning('Huaxin device sync failed: %s', e)

    @api.model
    def _cron_pull_temperatures(self):
        today = datetime.date.today()
        began = (today - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
        end = today.strftime('%Y-%m-%d')
        for machine in self.env['softlife.machine'].search([('device_imei', '!=', False)]):
            try:
                self.pull_temperatures(machine, began, end)
            except Exception as e:
                _logger.warning('Huaxin temperature pull failed for %s: %s', machine.display_name, e)

    # ------------------------------------------------------------------
    # Time parsing (source tz -> UTC)
    # ------------------------------------------------------------------
    @api.model
    def _parse_time(self, value):
        if not value:
            return False
        if isinstance(value, (int, float)):
            v = float(value)
            secs = v / 1000.0 if v > 1e12 else v
            return fields.Datetime.to_string(datetime.datetime.utcfromtimestamp(secs))
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d'):
            try:
                dt = datetime.datetime.strptime(str(value), fmt)
                return self._to_utc(dt)
            except ValueError:
                continue
        return False

    @api.model
    def _to_utc(self, dt):
        try:
            import pytz
            src = pytz.timezone(self._param('softlife.huaxin.source_tz', 'Asia/Shanghai') or 'Asia/Shanghai')
            return fields.Datetime.to_string(src.localize(dt).astimezone(pytz.UTC))
        except Exception:
            return fields.Datetime.to_string(dt)

    # ------------------------------------------------------------------
    # Stub data (used until credentials are entered)
    # ------------------------------------------------------------------
    @api.model
    def _stub_response(self, path, extra=None):
        if path.endswith('/devices'):
            return {'code': 200, 'data': {'list': [
                {'deviceId': '10000001', 'deviceName': 'B84MAX-STUB-1', 'deviceImei': '867395075018172'},
                {'deviceId': '10000002', 'deviceName': 'B84MAX-STUB-2', 'deviceImei': '867395075018173'},
            ]}}
        if path.endswith('/device/temperatures/trackings'):
            now = datetime.datetime.now()
            category = [(now - datetime.timedelta(minutes=10 * (9 - i))).strftime('%Y-%m-%d %H:%M:%S') for i in range(10)]
            data = [{'value': str(round(-4.0 - 0.4 * ((i * 7) % 5), 1))} for i in range(10)]
            return {'code': 200, 'data': {
                'category': category,
                'dataset': [{'seriesname': 'Cylinder temperature', 'data': data}],
            }}
        return {'code': 200, 'data': {}, 'result': True}
