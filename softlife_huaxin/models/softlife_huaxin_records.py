import json

from odoo import api, fields, models


class SoftlifeMachine(models.Model):
    """Extend the machine record with Huaxin-sourced telemetry relations."""
    _inherit = 'softlife.machine'

    huaxin_last_sync = fields.Datetime(string='Huaxin Last Sync', tracking=True)
    temperature_ids = fields.One2many('softlife.huaxin.temperature', 'machine_id')
    huaxin_order_ids = fields.One2many('softlife.huaxin.order', 'machine_id')
    fault_ids = fields.One2many('softlife.huaxin.fault', 'machine_id')

    temperature_count = fields.Integer(compute='_compute_huaxin_counts')
    order_count = fields.Integer(compute='_compute_huaxin_counts')
    fault_count = fields.Integer(compute='_compute_huaxin_counts')
    open_fault_count = fields.Integer(compute='_compute_huaxin_counts')

    def _compute_huaxin_counts(self):
        for rec in self:
            rec.temperature_count = len(rec.temperature_ids)
            rec.order_count = len(rec.huaxin_order_ids)
            rec.fault_count = len(rec.fault_ids)
            rec.open_fault_count = len(rec.fault_ids.filtered(lambda f: f.state == 'new'))

    def action_sync_from_huaxin(self):
        self.ensure_one()
        self.env['softlife.huaxin.client'].sync_devices()
        return True

    def action_open_temperatures(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': 'Temperatures',
            'res_model': 'softlife.huaxin.temperature', 'view_mode': 'list,graph',
            'domain': [('machine_id', '=', self.id)],
            'context': {'default_machine_id': self.id},
        }

    def action_open_orders(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': 'Machine Orders',
            'res_model': 'softlife.huaxin.order', 'view_mode': 'list,form',
            'domain': [('machine_id', '=', self.id)],
            'context': {'default_machine_id': self.id},
        }

    def action_open_faults(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': 'Faults / Alerts',
            'res_model': 'softlife.huaxin.fault', 'view_mode': 'list,form',
            'domain': [('machine_id', '=', self.id)],
            'context': {'default_machine_id': self.id},
        }


class SoftlifeHuaxinTemperature(models.Model):
    _name = 'softlife.huaxin.temperature'
    _description = 'Huaxin Machine Temperature Reading'
    _order = 'reading_time desc'

    machine_id = fields.Many2one('softlife.machine', string='Machine', ondelete='cascade')
    reading_time = fields.Datetime(string='Time', required=True, index=True)
    series_name = fields.Char(string='Series', help='e.g. "Pre cooling cylinder measured temperature".')
    value = fields.Float()
    raw = fields.Text()


class SoftlifeHuaxinOrder(models.Model):
    _name = 'softlife.huaxin.order'
    _description = 'Huaxin Machine Order (webhook + pull)'
    _order = 'order_time desc'

    machine_id = fields.Many2one('softlife.machine', string='Machine', ondelete='set null')
    device_imei = fields.Char(index=True)
    order_code = fields.Char(string='Huaxin Order #', index=True)
    out_trade_no = fields.Char(string='Payment Ref')
    order_state = fields.Char()  # PAID | FAILURE | COMPLETE
    order_time = fields.Datetime(index=True)
    price = fields.Float()
    amount = fields.Float(string='Dispensed Qty')
    product_name = fields.Char()
    detail_raw = fields.Text(string='Ingredient Detail (raw)')
    raw = fields.Text()


class SoftlifeHuaxinFault(models.Model):
    _name = 'softlife.huaxin.fault'
    _description = 'Huaxin Device Fault / Alert'
    _order = 'received_at desc'
    _inherit = ['mail.thread']

    machine_id = fields.Many2one('softlife.machine', string='Machine', ondelete='set null')
    device_id_huaxin = fields.Char(index=True)
    subject = fields.Char(tracking=True)
    html_body = fields.Text()
    received_at = fields.Datetime(index=True)
    state = fields.Selection(
        [('new', 'New'), ('acknowledged', 'Acknowledged'), ('resolved', 'Resolved')],
        default='new', tracking=True,
    )
    raw = fields.Text()
