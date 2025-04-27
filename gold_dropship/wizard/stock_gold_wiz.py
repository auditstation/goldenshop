# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
import logging

_logger = logging.getLogger(__name__)


class StockGoldWizard(models.TransientModel):
    _name = 'stock.gold'
    _description = 'Customize the information to open a purchase order for it.'

    price_per_gram = fields.Float('Price broken gold/g')
    location_ids = fields.Many2many('stock.location',domain=[("usage", "=", "internal")])


    def open_view_report(self):
        datas = {
            'model': 'stock.gold',
            'data': self.get_data() or {},
            }
        return self.env.ref('gold_dropship.action_report_gold_dashboard').report_action(self, data=datas)


    def get_data(self):
        StockQuant = self.env['stock.quant'].sudo()
        Product = self.env['product.product']
        currency = self.env.user.company_id.currency_id
    
        # Base domain
        domain = [("location_id.usage", "=", "internal")]
        if self.location_ids:
            domain.append(('location_id', 'in', self.location_ids.ids))
    
        # ---- Gold (not broken) ----
        domain_gold = domain + [('product_id.broken_gold', '=', False)]
        gold_quants = StockQuant.search(domain_gold)
        gold_products = gold_quants.mapped('product_id')
    
        total_gold_qty = sum(p.qty_available - p.incoming_qty for p in gold_products)
    
        # total_virtual_value = sum(p.standard_price * (p.qty_available - p.incoming_qty) for p in gold_products)
        # total_available_value = sum(gold_products.mapped('qty_available'))
        po_rec = self.env['purchase.order.line'].sudo().search(['&', ('state', 'in', ['purchase', 'done']), ('product_id', 'in', self.ids)])
        # total_virtual_value = sum(po_rec.mapped('price_total'))
        total_virtual_value = sum(i.currency_id._convert(
                    i.price_total,
                    self.env.company.currency_id,
                    self.env.company,
                    i.date_approve) for i in po_rec)
        total_available_value = sum(po_rec.mapped('product_qty'))
        gold_valuation = 0.0
        if total_available_value:
            gold_valuation = round(total_virtual_value / total_available_value,2)
    
        # ---- Broken Gold ----
        domain_broken = domain + [('product_id.broken_gold', '=', True)]
        broken_quants = StockQuant.search(domain_broken)
        broken_products = broken_quants.mapped('product_id')
    
        broken_gold_qty = sum(p.qty_available - p.incoming_qty for p in broken_products)
        broken_gold_valuation = broken_gold_qty * self.price_per_gram
    
        return {
            'gold_qty': total_gold_qty or 0.0,
            'gold_valuation': gold_valuation or 0.0,
            'broken_gold_qty': broken_gold_qty or 0.0,
            'broken_gold_valuation': broken_gold_valuation or 0.0,
            'currency': currency or '',
        }
