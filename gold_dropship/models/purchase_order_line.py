# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from datetime import timezone, datetime, date
from odoo.exceptions import ValidationError
import logging
import requests
import json
import re
_logger = logging.getLogger(__name__)

class PurchaseGoldInfo(models.Model):
    _name = "purchase.gold.info"
    
    po_line = fields.Many2one('purchase.order.line',copy=False)
    order_id = fields.Many2one(related='po_line.order_id',copy=False)
    gold_id = fields.Many2one('purchase.gold',copy=False)
    product_id = fields.Many2one(related='po_line.product_id',copy=False)
    partner_id = fields.Many2one(related='po_line.partner_id',copy=False)
    currency_id_iqd = fields.Many2one('res.currency',string='Currency',default=lambda self: self.env.company.currency_id.id,tracking=True)
    price_unit_iqd = fields.Monetary(related='po_line.price_unit_iqd',currency_field="currency_id_iqd",store=True,aggregator="avg")
    price_subtotal_iqd = fields.Monetary(related='po_line.price_subtotal_iqd',currency_field="currency_id_iqd",store=True)
    price_total_iqd = fields.Monetary(related='po_line.price_total_iqd',currency_field="currency_id_iqd",store=True)
    quantity_purchase = fields.Float(related='po_line.quantity_purchase',store=True) 
    qty = fields.Float()
    # USD Fields
    currency_id_usd = fields.Many2one('res.currency',string='Currency',default=lambda self: self.env.ref('base.USD').id,tracking=True)
    price_unit_usd = fields.Monetary(related='po_line.price_unit_usd',currency_field="currency_id_usd",store=True,aggregator="avg")
    price_subtotal_usd = fields.Monetary(related='po_line.price_subtotal_usd',currency_field="currency_id_usd",store=True)
    price_total_usd = fields.Monetary(related='po_line.price_total_usd',currency_field="currency_id_usd",store=True)
    
class PurchaseOrderLineInherit(models.Model):
    _inherit = "purchase.order.line"
    _rec_name='order_id'

    purity = fields.Float(string='Purity',copy=False)
    pure_gold = fields.Float(string='Pure Gold', compute='_compute_pure_gold')
    qty_check = fields.Boolean(copy=False)
    gold_ids = fields.Many2many('purchase.gold',copy=False)
    requested_qty = fields.Float(copy=False)
    currency_id_iqd = fields.Many2one('res.currency',string='Currency',default=lambda self: self.env.company.currency_id.id,tracking=True)
    price_unit_iqd = fields.Monetary(compute="_compute_prices_iqd",currency_field="currency_id_iqd",store=True)
    price_subtotal_iqd = fields.Monetary(compute="_compute_prices_iqd",currency_field="currency_id_iqd",store=True)
    price_total_iqd = fields.Monetary(compute="_compute_prices_iqd",currency_field="currency_id_iqd",store=True)
    quantity_purchase = fields.Float(compute="_compute_prices_iqd",store=True) 
    # USD Fields
    currency_id_usd = fields.Many2one('res.currency',string='Currency',default=lambda self: self.env.ref('base.USD').id,tracking=True)
    price_unit_usd = fields.Monetary(compute="_compute_prices_usd",currency_field="currency_id_usd",store=True)
    price_subtotal_usd = fields.Monetary(compute="_compute_prices_usd",currency_field="currency_id_usd",store=True)
    price_total_usd = fields.Monetary(compute="_compute_prices_usd",currency_field="currency_id_usd",store=True)
    
    @api.depends('price_unit')
    def _compute_prices_usd(self):
        usd_currency = self.env.ref('base.USD')
        for rec in self:
            rec.price_unit_usd = rec.currency_id._convert(
                        rec.price_unit,
                        usd_currency,
                        rec.company_id,
                        fields.Date.today(),)
            rec.price_subtotal_usd = rec.currency_id._convert(
                        rec.price_subtotal,
                        usd_currency,
                        rec.company_id,
                        fields.Date.today(),)
            rec.price_total_usd = rec.currency_id._convert(
                        rec.price_total,
                        usd_currency,
                        rec.company_id,
                        fields.Date.today(),)
            
            

    
    @api.depends('price_unit')
    def _compute_prices_iqd(self):
        iqd_currency = self.env.company.currency_id
        for rec in self:
            rec.price_unit_iqd = rec.currency_id._convert(
                        rec.price_unit,
                        iqd_currency,
                        rec.company_id,
                        fields.Date.today(),)
            rec.price_subtotal_iqd = rec.currency_id._convert(
                        rec.price_subtotal,
                        iqd_currency,
                        rec.company_id,
                        fields.Date.today(),)
            rec.price_total_iqd = rec.currency_id._convert(
                        rec.price_total,
                        iqd_currency,
                        rec.company_id,
                        fields.Date.today(),)
            rec.quantity_purchase = self.convert_to_gram(rec.product_qty,self.product_uom)
            
     
    def convert_to_gram(self, qty, uom):
        qty_gram = 0
        
        if uom.factor_inv == 1:
            qty_gram = qty * 1000
        elif uom.factor_inv < 1 and self.env.ref('uom.product_uom_gram').id != uom.id:
            qty_gram = (qty * uom.ratio) / 1000
        elif self.env.ref('uom.product_uom_gram').id == uom.id:
            qty_gram = qty
        return qty_gram

    @api.depends('product_qty', 'purity')
    def _compute_pure_gold(self):
        for rec in self:
            rec.pure_gold = rec.product_qty * rec.purity

    
    @api.depends('product_qty', 'price_unit', 'taxes_id', 'discount','purity','pure_gold')
    def _compute_amount(self):
        for line in self:
            base_line = line._prepare_base_line_for_taxes_computation()
            self.env['account.tax']._add_tax_details_in_base_line(base_line, line.company_id)
            line.price_subtotal = base_line['tax_details']['raw_total_excluded_currency']
            line.price_total = base_line['tax_details']['raw_total_included_currency']
            line.price_tax = line.price_total - line.price_subtotal

    # def _prepare_account_move_line(self, move=False):
    #     res = super(PurchaseOrderLineInherit, self)._prepare_account_move_line()
    #     res.update({"purity": self.purity})
    #     return res

    @api.depends('product_qty', 'product_uom', 'company_id', 'order_id.partner_id','product_id')
    def _compute_price_unit_and_date_planned_and_name(self):
        for line in self:
            super()._compute_price_unit_and_date_planned_and_name()
            if line.product_id.is_gold or line.product_id.broken_gold:
                base_url = self.env['ir.config_parameter'].sudo().get_param('report.url') or self.env[
                'ir.config_parameter'].sudo().get_param('web.base.url')
                url = base_url + '/gold_dropship/api/get_price'
                headers = {"Content-Type": "application/json", "Accept": "application/json",
                           "Catch-Control": "no-cache", }
                create_request_get_data = requests.get(url, data=json.dumps({}), headers=headers)
                response_body_data = json.loads(create_request_get_data.content)['result']
                usd_currency = self.env.ref('base.USD')
                if line.product_id.is_gold or line.product_id.broken_gold:
                    if re.search(r'\d+', line.product_id.display_name):
                        type_gold = int(re.search(r'\d+', line.product_id.display_name).group())
                price_gold_type = response_body_data/31.1035 * type_gold / 24 if re.search(r'\d+', line.product_id.display_name) else response_body_data/31.1035
                if line.product_uom.factor_inv == 1:
                    price_gold_type = price_gold_type * 1000
                elif line.product_uom.factor_inv < 1 and self.env.ref('uom.product_uom_gram').id != line.product_uom.id:
                    price_gold_type = (price_gold_type * line.product_uom.ratio) / 1000
                unit_price_iq= usd_currency._convert(
                        price_gold_type,
                        line.order_id.currency_id,
                        line.company_id,
                        fields.Date.today(),)
                converted_price = unit_price_iq 
                line.price_unit =converted_price
               


    
    # def write(self,vals):
    #     if 'purity' in vals and vals['purity']:
    #         for i in self.invoice_lines:
    #             i.with_context({'no_need_edit':True}).write({'purity':vals['purity']})
                
    #     return super().write(vals)

   