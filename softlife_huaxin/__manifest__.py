{
    'name': 'SoftLife Huaxin Bridge',
    'version': '18.0.1.0.0',
    'summary': 'Bridge to the Huaxin machine cloud: auth, signing, device sync, webhooks, telemetry.',
    'description': """
SoftLife Huaxin Bridge
======================
Reusable client (bridge) between Odoo and the Huaxin ice-cream machine cloud.
- MD5-signed, session-authenticated outbound calls
- Inbound webhook receiver (/huaxin/notify) for device faults and order events
- Device sync -> softlife.machine (matched by device_imei)
- Temperature ingestion for HACCP logging
- Built-in STUB MODE: when Huaxin has not yet issued credentials, returns
  canned data so the rest of the system is demoable.

Other modules (softlife_haccp, future orders/VeriFactu) depend on this and
never talk to Huaxin directly.
""",
    'author': 'SoftLife',
    'website': 'https://softlife.es',
    'category': 'Extra Tools/API',
    'license': 'OPL-1',
    'depends': ['softlife_machine'],
    'data': [
        'security/ir.model.access.csv',
        'data/softlife_huaxin_data.xml',
        'data/ir_cron.xml',
        'views/res_config_settings_views.xml',
        'views/softlife_huaxin_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': False,
}
