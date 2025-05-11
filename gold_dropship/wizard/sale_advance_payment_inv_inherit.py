# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from datetime import timezone, datetime, date
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class SaleAdvancePaymentInv(models.TransientModel):
    _inherit = 'sale.advance.payment.inv'
    def _create_invoices(self, sale_orders):
        inv = super()._create_invoices(self.sale_order_ids)
        if self.advance_payment_method == 'delivered':
            self.update_inv(inv)
        return inv

    def update_inv(self, inv):
        inv.payment_method = self.sale_order_ids.payment_method
        inv.invoice_line_ids= [(0,0, 
            {'display_type':'line_section','name':'Gold Sold',},)]
        inv.invoice_line_ids= [(0,0, 
        {
            'product_id': line.product_id.id,
            'product_uom_id': line.product_uom.id,
            'quantity': line.product_qty,
            'discount': line.discount,
            'price_unit': line.currency_id._convert(
                    line.price_unit * -1,
                    inv.currency_id,
                    inv.company_id,
                    fields.Date.today(),),
            'tax_ids': [(6, 0, line.taxes_id.ids)],
        }) for line in self.sale_order_ids.po_id.mapped('order_line')]
            