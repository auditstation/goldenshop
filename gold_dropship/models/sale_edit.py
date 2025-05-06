# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from datetime import timezone, datetime, date
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class SaleOrderInherit(models.Model):
    _inherit = 'sale.order'

    payment_method = fields.Selection(string='Payment Method', selection=[
        ('cash', 'Cash'),
        ('gold', 'Cash & Gold'),
    ], required=True, default='cash', readonly=True,copy=False)
    po_id = fields.Many2one('purchase.order', readonly=True,copy=False)
    def action_confirm(self):
        if not self.env.context.get('no_check') :
            return self.open_po_info_wizard()
        return super(SaleOrderInherit, self).action_confirm()

    def action_cancel(self):
        if self.po_id and self.payment_method == 'gold':
            self.po_id.button_cancel()
        return super(SaleOrderInherit, self).action_cancel()

    def open_po_info_wizard(self):
        product_id = self.find_gold_product()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Purchase Information',
            'res_model': 'po.info.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_id': self.id,
                'active_model': 'sale.order',
                'default_product_id': product_id.id,
                'default_sale_id': self.id,
            }
        }

    def find_gold_product(self):
        return self.env['product.product'].search([('purchase_ok', '=', True), ('broken_gold', '=', True)], limit=1)

    def action_view_purchase_orders_related(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Purchase Order',
            'res_model': 'purchase.order',
            'view_mode': 'tree,form',
            'views': [(False, 'list'), (False, 'form')],
            # or 'domain': [('from_sale', '=', self.name), ('company_id', '=', self.company_id.id)],
            'domain': [('id', '=', self.po_id.id), ('company_id', '=', self.company_id.id)],
            'context': {
                'active_id': self.id,
                'active_model': 'sale.order',
            }
        }
