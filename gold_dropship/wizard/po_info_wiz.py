# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
import logging
import requests
import json
import re
_logger = logging.getLogger(__name__)


class PoInfoWizard(models.TransientModel):
    _name = 'po.info.wizard'
    _description = 'Customize the information to open a purchase order for it.'

    payment_method = fields.Selection(string='Payment Method', selection=[
        ('cash', 'Cash'),
        ('gold', 'Cash & Gold'),
    ], required=True, default='cash')
    product_id = fields.Many2one('product.product', string='Product',
                                 domain=[('purchase_ok', '=', True), ('broken_gold', '=', True)],required=True)
    unit_price = fields.Float(related="product_id.standard_price", string="Unit Price", readonly=False)
    unit_price_update = fields.Float(string="Unit Price Updated", readonly=False,store=True)
    product_uom_id = fields.Many2one('uom.uom', string='Unit of Measure', domain="[('category_id', '=', product_uom_category_id)]",store=True)
    product_uom_category_id = fields.Many2one(related='product_id.uom_id.category_id')

    # product_uom_id = fields.Many2one('uom.uom', "Unit of Measure", compute="_compute_unit_price_update", readonly=False,store=True)
    qty = fields.Float(string='Quantity')
    supplier_taxes_id = fields.Many2many('account.tax', string="Purchase Taxes",
                                         readonly=False)
    sale_id = fields.Many2one('sale.order', readonly=True)
    currency_id = fields.Many2one('res.currency', readonly=False,default=lambda self:self.env.company.currency_id)
    company_id = fields.Many2one('res.company', readonly=True,
                                 default=lambda self:self.env.company,ondelete='cascade')
    
    check_true = fields.Boolean(readonly=True)

    def confirm_check(self):
        if self.payment_method == 'cash':
            self.confirm_button()
        else:
            self.check_true = True
            self.sale_id = self.sale_id.id
            return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'context':self.env.context,
            'view_mode': 'form',
            'target': 'new'}
        
    
    @api.onchange('payment_method','currency_id','product_id','product_uom_id')
    def _compute_unit_price_update(self):
        for rec in self:
            unit_price_update = 0
            base_url = self.env['ir.config_parameter'].sudo().get_param('report.url') or self.env[
            'ir.config_parameter'].sudo().get_param('web.base.url')
            url = base_url + '/gold_dropship/api/get_price'
            headers = {"Content-Type": "application/json", "Accept": "application/json",
                       "Catch-Control": "no-cache", }
            create_request_get_data = requests.get(url, data=json.dumps({}), headers=headers)
            unit_price_update = json.loads(create_request_get_data.content)['result']
            usd_currency = self.env.ref('base.USD')
            if rec.product_id.is_gold or rec.product_id.broken_gold:
                if re.search(r'\d+', rec.product_id.display_name):
                    type_gold = int(re.search(r'\d+', rec.product_id.display_name).group())
                price_gold_type = unit_price_update / 31.1035 * type_gold / 24 if re.search(r'\d+', rec.product_id.display_name) else unit_price_update
                if rec.product_uom_id.factor_inv == 1:
                    price_gold_type = price_gold_type * 1000
                elif rec.product_uom_id.factor_inv < 1 and self.env.ref('uom.product_uom_gram').id != rec.product_uom_id.id:
                    price_gold_type = (price_gold_type * rec.product_uom_id.ratio) / 1000
            unit_price_iq= usd_currency._convert(
                    price_gold_type,
                    rec.currency_id,
                    rec.company_id,
                    fields.Date.today(),)
            converted_price = unit_price_iq
            rec.unit_price_update = converted_price
           
    

        
    @api.onchange('product_id')
    def _onchange_product_id(self):
        for rec in self:
            if rec.product_id:
                rec.supplier_taxes_id = rec.product_id.with_company(self.env.company).supplier_taxes_id
            if not rec.product_id:
                return

            rec.product_uom_id = rec.product_id.uom_id.id
    
    def confirm_button(self):
        sale_order = self.sale_id
        if self.payment_method == 'gold' and not self.sale_id.po_id and self.check_true:
            self.create_po()
        elif self.payment_method == 'gold' and self.sale_id.po_id and self.check_true:
            self.edit_po(purchase_order=self.sale_id.po_id)
        sale_order.payment_method = self.payment_method
        sale_order.with_context({'no_check':True}).action_confirm()
        return True
        # return {'type': 'ir.actions.act_window_close'}

    def create_po(self):
        po = self.env['purchase.order'].with_context({'from_wiz':True}).create(self.get_data() or {})
        po.button_confirm()
        self.sale_id.po_id = po.id
    
    def edit_po(self, purchase_order):
        purchase_order.button_draft()
        purchase_order.order_line = [(5, 0, 0)]
        purchase_order.with_context({'from_wiz':True}).write(self.get_data() or {} )
        purchase_order.button_confirm()
        # self.sale_id.po_id = purchase_order.id

    def get_data(self):
        return {
            'partner_id': self.sale_id.partner_id.id,
            'date_order': self.sale_id.commitment_date or fields.Date.today(),
            'origin': self.sale_id.name,
            'currency_id':self.currency_id.id,
            # 'from_sale': self.sale_id.name,
            'order_line': [(0, 0, {
                'product_id': self.product_id.id,
                'product_qty': self.qty,
                'product_uom': self.product_uom_id.id,
                'price_unit': self.unit_price_update,
                'sale_order_id':self.sale_id.id,
                'taxes_id': [(6, 0, self.supplier_taxes_id.ids)]
            })],
        }
