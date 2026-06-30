"""Client tests: the fixed credential block is sent verbatim (no recomputation)."""
from odoo.tests.common import TransactionCase


class TestHuaxinClient(TransactionCase):

    def test_stub_when_unconfigured(self):
        self.assertTrue(self.env['softlife.huaxin.client']._is_stub())

    def test_static_block_passthrough_when_configured(self):
        icp = self.env['ir.config_parameter'].sudo()
        # Placeholder values — real credentials never live in the repo.
        icp.set_param('softlife.huaxin.base_url', 'https://example.huaxin.cloud')
        icp.set_param('softlife.huaxin.mch_id', 'TEST_MCH_ID')
        icp.set_param('softlife.huaxin.mch_secret', 'TEST_MCH_SECRET')
        icp.set_param('softlife.huaxin.sign', 'TEST_SIGN_STATIC')
        icp.set_param('softlife.huaxin.nonce_str', 'TEST_NONCE')
        icp.set_param('softlife.huaxin.time_stamp', '1579154268')

        client = self.env['softlife.huaxin.client']
        self.assertFalse(client._is_stub())

        common = client._common_params()
        # The sign is the static value Huaxin issued — passed through, never recomputed.
        self.assertEqual(common['sign'], 'TEST_SIGN_STATIC')
        self.assertEqual(common['mch_id'], 'TEST_MCH_ID')
        self.assertEqual(common['nonce_str'], 'TEST_NONCE')
        self.assertEqual(common['time_Stamp'], '1579154268')
