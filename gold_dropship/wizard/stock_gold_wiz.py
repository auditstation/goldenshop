# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
import logging
import requests
import json
import re

_logger = logging.getLogger(__name__)
from collections import defaultdict


class StockGoldWizard(models.TransientModel):
    _name = 'stock.gold'
    _description = 'Customize the information to open a purchase order for it.'

    price_per_gram = fields.Float('Price broken gold/kg (IQD)')
    location_ids = fields.Many2many('stock.location', domain=[("usage", "=", "internal")])
    calculation_gold_price = fields.Selection([('initial', 'Initial Market Price'),
                                               ('avg', 'Average Cost'),
                                               ], default='avg', required=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    def group_products_by_template(self, location_ids):

        grouped = defaultdict(lambda: {
            'template_name': '',
            'variants': []
        })

        products = self.env['product.product'].search([('is_gold', '=', True)])
        StockQuant = self.env['stock.quant'].sudo()
        domain = [("location_id.usage", "=", "internal"), ('company_id', '=', self.env.company.id)]
        if location_ids:
            domain.append(('location_id', 'in', location_ids.ids))

        for variant in products:
            template = variant.product_tmpl_id
            key = template.id
            domain_gold = domain + [('product_id.is_gold', '=', True), ('product_id', '=', variant.id)]
            grouped[key]['template_name'] = template.name
            grouped[key]['variants'].append({
                'variant_name': variant.display_name,
                'incoming': variant.incoming_qty,
                'onhand': sum(p.quantity for p in StockQuant.search(domain_gold))
            })

        return grouped

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
        domain = [("location_id.usage", "=", "internal"), ('company_id', '=', self.env.company.id)]
        if self.location_ids:
            domain.append(('location_id', 'in', self.location_ids.ids))
        # ---- Broken Gold ----
        domain_broken = domain + [('product_id.broken_gold', '=', True)]
        broken_quants = sum(p.quantity for p in StockQuant.search(domain_broken))
        broken_products = self.env['product.product'].search([('broken_gold', '=', True)])

        broken_gold_qty = broken_quants + sum(p.incoming_qty for p in broken_products)
        broken_gold_valuation = broken_gold_qty * self.price_per_gram
        # ---- Gold (not broken) ----
        domain_gold = domain + [('product_id.is_gold', '=', True)]
        gold_quants = sum(p.quantity for p in StockQuant.search(domain_gold))
        gold_products = self.env['product.product'].search([('is_gold', '=', True)])
        total_gold_qty = gold_quants + sum(p.incoming_qty for p in gold_products)
        # total_virtual_value = sum(p.standard_price * (p.qty_available - p.incoming_qty) for p in gold_products)
        # total_available_value = sum(gold_products.mapped('qty_available'))
        po_rec = self.env['purchase.order.line'].sudo().search(
            [('company_id', '=', self.company_id.id), ('state', 'in', ['purchase', 'done'])]).filtered(
            lambda l: l.product_id.is_gold)
        # total_virtual_value = sum(po_rec.mapped('price_total'))
        base_url = self.env['ir.config_parameter'].sudo().get_param('report.url') or self.env[
                'ir.config_parameter'].sudo().get_param('web.base.url')
        url = base_url + '/gold_dropship/api/get_price'
        headers = {"Content-Type": "application/json", "Accept": "application/json",
                   "Catch-Control": "no-cache", }
        create_request_get_data = requests.get(url, data=json.dumps({}), headers=headers)
        unit_price_update = json.loads(create_request_get_data.content)['result']

        usd_currency = self.env.ref('base.USD')
        calculation_gold_price =''
        if self.calculation_gold_price == 'avg':
            calculation_gold_price = self.calculation_gold_price
            # ---- Gold (not broken) ----
            total_virtual_value = sum(i.currency_id._convert(
                i.price_total,
                self.env.company.currency_id,
                self.env.company,
                i.date_approve) for i in po_rec)
            total_available_value = total_gold_qty
            gold_valuation = 0.0
            if total_available_value:
                gold_valuation = round(total_virtual_value / total_available_value)
        else:
            calculation_gold_price = 'initial'
            variants = self.group_products_by_template(self.location_ids if self.location_ids else [])
            gold_valuation_product = 0
            total_gold_qty1 = 0
            for template_id, template_data in variants.items():
                for variant in template_data['variants']:
                    price_gold_type = 0
                    name = variant.get('variant_name', '')
                    if re.search(r'\d+', name):
                        type_gold = int(re.search(r'\d+', name).group())
                    price_gold_type = unit_price_update/31.1035 * type_gold / 24 if re.search(r'\d+', name) else unit_price_update
                    name = variant.get('variant_name', '')
                    unit_price_iq = usd_currency._convert(
                        price_gold_type,
                        self.env.company.currency_id,
                        self.env.company,
                        fields.Date.today())
                    converted_price = unit_price_iq
                    qty_product = variant.get('onhand', 0) + variant.get('incoming', 0)
                    gold_valuation_product += round(qty_product * converted_price, 2)
                    total_gold_qty1 += qty_product
            gold_valuation = gold_valuation_product
            total_gold_qty = total_gold_qty1
       
        ounce = usd_currency._convert(unit_price_update, self.env.company.currency_id, self.env.company,
                                      fields.Date.today())
        karat_18 = usd_currency._convert(unit_price_update/ 31.1035 * 18 / 24 , self.env.company.currency_id, self.env.company,
                                      fields.Date.today())
        karat_21 = usd_currency._convert(unit_price_update/ 31.1035 * 21 / 24 , self.env.company.currency_id, self.env.company,
                                      fields.Date.today())
        karat_24 = usd_currency._convert(unit_price_update/ 31.1035, self.env.company.currency_id, self.env.company,
                                      fields.Date.today())

        gold_pure = sum([i.qty_gram for i in self.env['purchase.gold'].sudo().search([('state','=','available')])])
        unit_price_iq = usd_currency._convert(
                        unit_price_update / 31.1035,
                        self.env.company.currency_id,
                        self.env.company,
                        fields.Date.today(), )
        gold_pure_valuation = gold_pure * unit_price_iq
    
        return {
            'gold_qty': total_gold_qty or 0.0,
            'gold_valuation': gold_valuation or 0.0,
            'broken_gold_qty': broken_gold_qty or 0.0,
            'broken_gold_valuation': broken_gold_valuation or 0.0,
            'gold_pure':gold_pure or 0.0,
            'gold_pure_valuation':gold_pure_valuation or 0.0,
            'gold_valuation_usd':self.env.company.currency_id._convert(
                        gold_valuation,
                        usd_currency,
                        self.env.company,
                        fields.Date.today()) or 0.0,
            'broken_gold_valuation_usd':self.env.company.currency_id._convert(
                        broken_gold_valuation,
                        usd_currency,
                        self.env.company,
                        fields.Date.today()) or 0.0,
            'gold_pure_valuation_usd':self.env.company.currency_id._convert(
                        gold_pure_valuation,
                        usd_currency,
                        self.env.company,
                        fields.Date.today()) or 0.0,
            'currency': currency or '',
            'Ounce': ounce or 0.0,
            '18_karat': karat_18 or 0.0,
            '21_karat': karat_21 or 0.0,
            '24_karat': karat_24 or 0.0,
            '18_karat_usd':unit_price_update/ 31.1035 * 18 / 24 or 0.0,
            '21_karat_usd': unit_price_update/ 31.1035 * 21 / 24 or 0.0,
            '24_karat_usd': unit_price_update/ 31.1035  or 0.0,
            'calculation_gold_price':calculation_gold_price
        }
