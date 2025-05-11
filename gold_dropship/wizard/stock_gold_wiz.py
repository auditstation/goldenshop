# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
import logging
import requests
import json
_logger = logging.getLogger(__name__)


class StockGoldWizard(models.TransientModel):
    _name = 'stock.gold'
    _description = 'Customize the information to open a purchase order for it.'

    price_per_gram = fields.Float('Price broken gold/kg')
    location_ids = fields.Many2many('stock.location',domain=[("usage", "=", "internal")])
    calculation_gold_price = fields.Selection([('initial', 'Initial Market Price'),
                              ('avg', 'Average Cost'),
                              ], default='avg',required=True)

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
        domain = [("location_id.usage", "=", "internal"),('company_id','=',self.env.company.id)]
        if self.location_ids:
            domain.append(('location_id', 'in', self.location_ids.ids))
        # ---- Broken Gold ----
        domain_broken = domain + [('product_id.broken_gold', '=', True)]
        broken_quants = StockQuant.search(domain_broken)
        broken_products = broken_quants.mapped('product_id')
    
        broken_gold_qty = sum(p.qty_available + p.incoming_qty for p in broken_products)
        broken_gold_valuation = broken_gold_qty * self.price_per_gram
        # ---- Gold (not broken) ----
        domain_gold = domain + [('product_id.is_gold', '=', True)]
        gold_quants = StockQuant.search(domain_gold)
        gold_products = gold_quants.mapped('product_id')
        total_gold_qty = sum(p.qty_available + p.incoming_qty for p in gold_products)
        # total_virtual_value = sum(p.standard_price * (p.qty_available - p.incoming_qty) for p in gold_products)
        # total_available_value = sum(gold_products.mapped('qty_available'))
        po_rec = self.env['purchase.order.line'].sudo().search([('company_id','=',self.company_id.id),('state', 'in', ['purchase', 'done'])]).filtered(lambda l:l.product_id.is_gold)
        # total_virtual_value = sum(po_rec.mapped('price_total'))
        if self.calculation_gold_price == 'avg':
            # ---- Gold (not broken) ----
            total_virtual_value = sum(i.currency_id._convert(
                        i.price_total,
                        self.env.company.currency_id,
                        self.env.company,
                        i.date_approve) for i in po_rec)
            total_available_value = sum(po_rec.mapped('product_qty'))
            gold_valuation = 0.0
            if total_available_value:
                gold_valuation = round(total_virtual_value / total_available_value)
        else:
            unit_price_update = 0
            base_url = self.env['ir.config_parameter'].sudo().get_param('report.url') or self.env[
            'ir.config_parameter'].sudo().get_param('web.base.url')
            url = base_url + '/gold_dropship/api/get_price'
            headers = {"Content-Type": "application/json", "Accept": "application/json",
                       "Catch-Control": "no-cache", }
            create_request_get_data = requests.get(url, data=json.dumps({}), headers=headers)
            unit_price_update = json.loads(create_request_get_data.content)['result']
            usd_currency = self.env.ref('base.USD')
            unit_price_iq= usd_currency._convert(
                    unit_price_update,
                    self.env.company.currency_id,
                    self.env.company,
                    fields.Date.today(),)
            converted_price = unit_price_iq
            gold_valuation = round(total_gold_qty * converted_price ,2)
    
        return {
            'gold_qty': total_gold_qty or 0.0,
            'gold_valuation': gold_valuation or 0.0,
            'broken_gold_qty': broken_gold_qty or 0.0,
            'broken_gold_valuation': broken_gold_valuation or 0.0,
            'currency': currency or '',
        }
