# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from datetime import timezone, datetime, date
from odoo.exceptions import ValidationError
import logging
import requests
import json
import re
_logger = logging.getLogger(__name__)


class PurchaseOrderLineInherit(models.Model):
    _inherit = "purchase.order.line"

    purity = fields.Float(string='Purity')
    pure_gold = fields.Float(string='Pure Gold', compute='_compute_pure_gold')

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

    @api.depends('product_qty', 'product_uom', 'company_id', 'order_id.partner_id','order_id.currency_id','product_id')
    def _compute_price_unit_and_date_planned_and_name(self):
        super()._compute_price_unit_and_date_planned_and_name()

        for line in self:
            if line.product_id.is_gold or line.product_id.broken_gold:
                base_url = self.env['ir.config_parameter'].sudo().get_param('report.url') or self.env[
                'ir.config_parameter'].sudo().get_param('web.base.url')
                url = base_url + '/gold_dropship/api/get_price'
                headers = {"Content-Type": "application/json", "Accept": "application/json",
                           "Catch-Control": "no-cache", }
                create_request_get_data = requests.get(url, data=json.dumps({}), headers=headers)
                response_body_data = json.loads(create_request_get_data.content)['result']
                usd_currency = self.env.ref('base.USD')
                if self.product_id.is_gold or self.product_id.broken_gold:
                    if re.search(r'\d+', self.product_id.display_name):
                        type_gold = int(re.search(r'\d+', self.product_id.display_name).group())
                price_gold_type = response_body_data/31.1035 * type_gold / 24 if re.search(r'\d+', self.product_id.display_name) else response_body_data
                if line.product_uom.factor_inv == 1:
                    price_gold_type = price_gold_type * 1000
                elif line.product_uom.factor_inv < 1 and self.env.ref('uom.product_uom_gram').id != line.product_uom.id:
                    price_gold_type = (price_gold_type * line.product_uom.ratio) / 1000
                    
                unit_price_iq= usd_currency._convert(
                        price_gold_type,
                        line.currency_id,
                        line.company_id,
                        fields.Date.today(),)
                converted_price = unit_price_iq
               
                line.price_unit = converted_price


    
    # def write(self,vals):
    #     if 'purity' in vals and vals['purity']:
    #         for i in self.invoice_lines:
    #             i.with_context({'no_need_edit':True}).write({'purity':vals['purity']})
                
    #     return super().write(vals)

   