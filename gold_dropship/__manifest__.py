# -*- coding: utf-8 -*-
{
    'name': "Gold Dropship",
    'author': "Audit Station",
    'version': '18.0',
    'depends': ['base', 'mail', 'sale_management', 'sale_stock', 'purchase', 'stock', 'sale', 'product','mrp'],
    'application': True,
    'data': [
        'security/ir.model.access.csv',
        'data/data.xml',
        'wizard/po_info_view_wiz.xml',
        'wizard/stock_gold_wiz.xml',
        'wizard/gold_info_wiz_view.xml',
        'views/sale_view.xml',
        'views/account_move_view.xml',
        'views/purchase_order_view.xml',
        'views/product_inherit.xml',
        'views/mrp.xml',
        'views/purchase_gold.xml',
        'views/menu_item.xml',
        'report/gold_report.xml'
    ],
    'license': 'LGPL-3',
}
