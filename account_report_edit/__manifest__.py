# -*- coding: utf-8 -*-
{
    'name': "Gold Accounting Report",
    'author': "Audit Station",
    'version': '18.0',
    'depends': ['base', 'mail', 'account','account_reports'],
    'application': True,
    'data': [
        # 'views/account_report_view.xml',
          "views/account_move_line.xml"
    ],
    'assets': {
        'web.assets_backend': [
            'account_report_edit/static/src/components/line_name.xml',
        ],
    },
    'license': 'LGPL-3',
}
