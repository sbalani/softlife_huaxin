from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    huaxin_base_url = fields.Char(
        string='Huaxin Cloud Base URL',
        config_parameter='softlife.huaxin.base_url',
        help='Huaxin cloud API base (provided by Huaxin). Leave empty to run in stub mode.',
    )
    huaxin_mch_id = fields.Char(string='Merchant ID (mch_id)', config_parameter='softlife.huaxin.mch_id')
    huaxin_mch_secret = fields.Char(string='Merchant Secret (mch_secret)', config_parameter='softlife.huaxin.mch_secret')

    # The fixed credential block Huaxin issues — sent verbatim, not computed.
    huaxin_sign = fields.Char(
        string='Sign',
        config_parameter='softlife.huaxin.sign',
        help='Static sign value issued by Huaxin (part of the credential block).',
    )
    huaxin_nonce_str = fields.Char(string='Nonce (nonce_str)', config_parameter='softlife.huaxin.nonce_str')
    huaxin_time_stamp = fields.Char(string='Timestamp (time_Stamp)', config_parameter='softlife.huaxin.time_stamp')

    huaxin_notify_url = fields.Char(
        string='Webhook URL (notify_url)',
        config_parameter='softlife.huaxin.notify_url',
        help='The public Odoo URL Huaxin posts order/fault events to.',
    )
    huaxin_notify_token = fields.Char(
        string='Webhook Shared Token',
        config_parameter='softlife.huaxin.notify_token',
        help='Optional secret. If set, inbound webhooks must send it as ?token= or X-Huaxin-Token header.',
    )
    huaxin_source_tz = fields.Char(
        string='Huaxin Source Timezone',
        config_parameter='softlife.huaxin.source_tz',
        default='Asia/Shanghai',
        help='Timezone Huaxin sends timestamps in (default East Asia). We convert to UTC on import.',
    )
    huaxin_display_tz = fields.Char(
        string='Display Timezone',
        config_parameter='softlife.huaxin.display_tz',
        default='Europe/Madrid',
    )
    huaxin_verify_ssl = fields.Boolean(
        string='Verify SSL Certificate',
        config_parameter='softlife.huaxin.verify_ssl',
        default=True,
        help='Disable ONLY for the UAT server, whose certificate is currently expired.',
    )

    huaxin_is_stub = fields.Boolean(string='Stub mode active', compute='_compute_huaxin_is_stub')

    @api.depends('huaxin_base_url', 'huaxin_mch_id', 'huaxin_mch_secret', 'huaxin_sign')
    def _compute_huaxin_is_stub(self):
        for rec in self:
            rec.huaxin_is_stub = not (rec.huaxin_base_url and rec.huaxin_mch_id
                                     and rec.huaxin_mch_secret and rec.huaxin_sign)
