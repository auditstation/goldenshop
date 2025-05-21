# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from datetime import timezone, datetime, date
from odoo.exceptions import ValidationError
import logging
import requests
import json
import re
from odoo.tools.float_utils import float_compare, float_round
_logger = logging.getLogger(__name__)


class PurchaseGold(models.Model):
    _name = "purchase.gold"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']

    name = fields.Char(string="Reference", readonly=True, copy=False, default='New')
    date = fields.Date(string="Date", default=fields.Date.today)
    partner_id = fields.Many2one('res.partner', string='Vendor', required=True, change_default=True, check_company=True,tracking=True)
    product_id = fields.Many2one('product.product', string='Product', domain=[('purchase_ok', '=', True)], change_default=True,tracking=True)
    quantity = fields.Float('Quantity',default=1,compute="_compute_qty",readonly=False,store=True,tracking=True,digits=(16, 3))
    qty_gram = fields.Float(compute="_compute_qty_gram",string='Quantity(g)',store=True,copy=False)
    product_uom = fields.Many2one('uom.uom', string='Unit of Measure', domain="[('category_id', '=', product_uom_category_id)]",store=True,tracking=True)
    product_uom_category_id = fields.Many2one(related='product_id.uom_id.category_id')
    company_id = fields.Many2one('res.company', readonly=True,
                                 default=lambda self:self.env.company,ondelete='cascade')
    tranfer_qty = fields.Float(compute="_compute_transfer_qty",store=True,string="Delivered Quantity",copy=False)
    all_qty = fields.Float(store=True,string="Quantity",copy=False)
    all_qty_g = fields.Float(compute="_compute_all_qty_g",store=True,string="Quantity(g)",copy=False)
    price_unit = fields.Monetary(
        string='Unit Price', required=True,aggregator='sum',
        compute="_compute_price_unit_and_date_planned_and_name", readonly=False, store=True,digits=(16, 3),tracking=True)
    currency_id = fields.Many2one('res.currency',string='Currency',default=lambda self: self.env.company.currency_id.id,tracking=True)
    currency_id_iqd = fields.Many2one('res.currency',string='Currency',default=lambda self: self.env.company.currency_id.id,tracking=True)
    price_unit_iqd = fields.Monetary(compute="_compute_price_iqd",store=True,currency_field="currency_id_iqd",string="Price Unit IQD",aggregator="avg")
    taxes_id = fields.Many2many('account.tax', string='Taxes', context={'active_test': False},tracking=True)
    total_amount_excl = fields.Monetary(compute="_compute_total", aggregator='sum',store=True,string="Amount without tax",digits=(16, 3))
    total_amount_excl_iqd = fields.Monetary(compute="_compute_total", aggregator='sum',store=True,string="Amount without tax IQD",digits=(16, 3),currency_field="currency_id_iqd")
    total_amount_incl = fields.Monetary(compute="_compute_total", aggregator='sum',store=True,string="Total",digits=(16, 3))
    total_amount_incl_iqd = fields.Monetary(compute="_compute_total", aggregator='sum',store=True,string="Total",digits=(16, 3),currency_field="currency_id_iqd")
    state = fields.Selection([
        ('available', 'Avaliable'),
        ('not', 'Not Avaliable')],default='available')

    po_line = fields.Many2many('purchase.order.line',copy=False)
    po_gold_line = fields.Many2many('purchase.gold.info',copy=False,string="Po gold")
    is_appear = fields.Boolean(compute="compute_appear_prices")
    is_appear_gram = fields.Boolean(compute="compute_gram")
    all_price_unit_iqd = fields.Monetary(compute="_compute_total_data",currency_field="currency_id_iqd",store=True,aggregator="avg")
    all_price_subtotal_iqd = fields.Monetary(compute="_compute_total_data",currency_field="currency_id_iqd",store=True)
    all_price_total_iqd = fields.Monetary(compute="_compute_total_data",currency_field="currency_id_iqd",store=True)
    all_quantity_purchase = fields.Float(compute="_compute_total_data",store=True) 
    difference_total = fields.Float('difference',compute="_compute_total_data",store=True)
    # USD Fields
    currency_id_usd = fields.Many2one('res.currency',string='Currency',default=lambda self: self.env.ref('base.USD').id,tracking=True)
    price_unit_usd = fields.Monetary(compute="_compute_price_usd",store=True,currency_field="currency_id_usd",string="Price Unit USD",aggregator="avg")
    total_amount_excl_usd = fields.Monetary(compute="_compute_total_usd", aggregator='sum',store=True,string="Amount without tax USD",digits=(16, 3),currency_field="currency_id_usd")
    total_amount_incl_usd = fields.Monetary(compute="_compute_total_usd", aggregator='sum',store=True,string="Total USD",digits=(16, 3),currency_field="currency_id_usd")
    all_price_unit_usd = fields.Monetary(compute="_compute_total_data_usd",currency_field="currency_id_usd",store=True,aggregator="avg")
    all_price_subtotal_usd = fields.Monetary(compute="_compute_total_data_usd",currency_field="currency_id_usd",store=True)
    all_price_total_usd = fields.Monetary(compute="_compute_total_data_usd",currency_field="currency_id_usd",store=True)
    difference_total_usd = fields.Float('difference',compute="_compute_total_data_usd",store=True)
    
    @api.depends('price_unit','currency_id')
    def _compute_price_usd(self):
        usd_currency = self.env.ref('base.USD')
        for rec in self:
            rec.price_unit_usd = rec.currency_id._convert(
                        rec.price_unit,
                        usd_currency,
                        rec.company_id,
                        fields.Date.today(),)

    @api.depends('product_id','quantity','price_unit','taxes_id')
    def _compute_total_usd(self):
        usd_currency = self.env.ref('base.USD')
        for rec in self:
            rec.total_amount_excl_usd = rec.currency_id._convert(
                        rec.total_amount_incl,
                        usd_currency,
                        rec.company_id,
                        fields.Date.today(),)
            rec.total_amount_incl_usd = rec.currency_id._convert(
                        rec.total_amount_incl,
                        usd_currency,
                        rec.company_id,
                        fields.Date.today(),)
    @api.depends('po_gold_line')
    def _compute_total_data_usd(self):
        for rec in self:
            rec.all_price_unit_usd = sum([i.price_unit_usd for i in rec.po_gold_line])/len(rec.po_gold_line) if rec.po_gold_line else 0
            rec.all_price_subtotal_usd = sum([i.price_subtotal_usd for i in rec.po_gold_line])
            rec.all_price_total_usd = sum([i.price_total_usd for i in rec.po_gold_line])
            rec.difference_total_usd = rec.total_amount_incl_usd - rec.all_price_total_usd

    
    @api.depends('po_gold_line')
    def _compute_total_data(self):
        for rec in self:
            rec.all_price_unit_iqd = sum([i.price_unit_iqd for i in rec.po_gold_line])/len(rec.po_gold_line) if rec.po_gold_line else 0
            rec.all_price_subtotal_iqd = sum([i.price_subtotal_iqd for i in rec.po_gold_line])
            rec.all_price_total_iqd = sum([i.price_total_iqd for i in rec.po_gold_line])
            rec.all_quantity_purchase = sum([i.quantity_purchase for i in rec.po_gold_line])
            rec.difference_total = rec.total_amount_incl_iqd - rec.all_price_total_iqd
   
    @api.depends('currency_id')
    def compute_appear_prices(self):
        for rec in self:
            rec.is_appear = True if rec.currency_id_iqd.id != rec.currency_id.id else False
    
    @api.depends('product_id','product_uom')
    def compute_gram(self):
        for rec in self:
            if rec.product_uom.id:
                rec.is_appear_gram = True if rec.product_uom.id != self.env.ref('uom.product_uom_gram').id else False
            else:
                rec.is_appear_gram = False

    @api.onchange('quantity')
    def _change_qty(self):
        if self.quantity and self.quantity > 0 and self.id:
            raise ValidationError("You can't put quantity in minus")
    
    @api.depends('quantity','product_uom')
    def _compute_all_qty_g(self):     
        for rec in self:
            rec.all_qty_g = rec.qty_gram + sum([i.qty for i in rec.po_gold_line])

    @api.depends('product_id','quantity','price_unit','taxes_id')
    def _compute_total(self):
        iqd_currency = self.env.company.currency_id
        for rec in self:
            tax = sum([i.amount/100 for i in rec.taxes_id])
            amount_tax = rec.quantity * rec.price_unit * tax 
            rec.total_amount_excl = rec.quantity * rec.price_unit
            rec.total_amount_incl = (rec.quantity * rec.price_unit) + amount_tax
            if rec.tranfer_qty != 0:
                rec.total_amount_excl = rec.tranfer_qty * rec.price_unit
                rec.total_amount_incl = (rec.tranfer_qty * rec.price_unit) + amount_tax
            rec.total_amount_excl_iqd = rec.currency_id._convert(
                        rec.total_amount_incl,
                        iqd_currency,
                        rec.company_id,
                        fields.Date.today(),)
            rec.total_amount_incl_iqd = rec.currency_id._convert(
                        rec.total_amount_incl,
                        iqd_currency,
                        rec.company_id,
                        fields.Date.today(),)

    @api.depends('price_unit','currency_id')
    def _compute_price_iqd(self):
        iqd_currency = self.env.company.currency_id
        for rec in self:
            rec.price_unit_iqd = rec.currency_id._convert(
                        rec.price_unit,
                        iqd_currency,
                        rec.company_id,
                        fields.Date.today(),)
            

    @api.depends('po_gold_line')
    def _compute_transfer_qty(self):
        for rec in self:
            rec.tranfer_qty = sum([i.qty for i in rec.po_gold_line])
            
           
    @api.depends('po_gold_line')
    def _compute_qty(self):
        for rec in self:
            quantity = 0
            # if rec.po_gold_line:
            requested_qty =  rec.tranfer_qty
            if rec.product_uom.factor_inv == 1:
                quantity = rec.all_qty - (requested_qty /1000)
            elif rec.product_uom.factor_inv < 1 and self.env.ref('uom.product_uom_gram').id != rec.product_uom.id:
                quantity =  rec.all_qty - ((requested_qty * rec.product_uom.ratio) * 1000)
            elif self.env.ref('uom.product_uom_gram').id == rec.product_uom.id:
                quantity = rec.all_qty - requested_qty
            rec.quantity = quantity
            if quantity == 0:
                rec.state = 'not'
            
                    
    @api.depends('quantity', 'product_uom','po_gold_line')
    def _compute_qty_gram(self):
        for rec in self:
            qty_gram = 0
            if rec.product_uom.factor_inv == 1:
                qty_gram = (rec.quantity * 1000)
            elif rec.product_uom.factor_inv < 1 and self.env.ref('uom.product_uom_gram').id != rec.product_uom.id:
                qty_gram = ((rec.quantity * rec.product_uom.ratio) / 1000)
            elif self.env.ref('uom.product_uom_gram').id == rec.product_uom.id:
                qty_gram = rec.quantity
            rec.qty_gram = qty_gram
    
    
    @api.depends('currency_id','product_id','product_uom')
    def _compute_price_unit_and_date_planned_and_name(self):
        for line in self:
            if not line.product_id or not line.company_id:
                continue
            if line.product_id.is_gold:
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
                price_gold_type = response_body_data/31.1035 * type_gold / 24 if re.search(r'\d+', self.product_id.display_name) else response_body_data/31.1035
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
            else:
                seller = line.product_id._select_seller(
                    partner_id=line.partner_id,
                    quantity=line.quantity,
                    date=line.date or fields.Date.context_today(line),
                    uom_id=line.product_uom,
                    params=False)
                if not seller:
                    
                    unavailable_seller = line.product_id.seller_ids.filtered(
                        lambda s: s.partner_id == line.partner_id)
                    if not unavailable_seller and line.price_unit and line.product_uom == line._origin.product_uom:
                        continue
                    po_line_uom = line.product_uom or line.product_id.uom_po_id
                    price_unit = line.env['account.tax']._fix_tax_included_price_company(
                        line.product_id.uom_id._compute_price(line.product_id.standard_price, po_line_uom),
                        line.product_id.supplier_taxes_id,
                        line.taxes_id,
                        line.company_id,
                    )
                    price_unit = line.product_id.cost_currency_id._convert(
                        price_unit,
                        line.currency_id,
                        line.company_id,
                        line.date or fields.Date.context_today(line),
                        False
                    )
                    line.price_unit = float_round(price_unit, precision_digits=max(line.currency_id.decimal_places, self.env['decimal.precision'].precision_get('Product Price')))
    
                elif seller:
                    price_unit = line.env['account.tax']._fix_tax_included_price_company(seller.price, line.product_id.supplier_taxes_id, line.taxes_id, line.company_id) if seller else 0.0
                    price_unit = seller.currency_id._convert(price_unit, line.currency_id, line.company_id, line.date or fields.Date.context_today(line), False)
                    price_unit = float_round(price_unit, precision_digits=max(line.currency_id.decimal_places, self.env['decimal.precision'].precision_get('Product Price')))
                    line.price_unit = seller.product_uom._compute_price(price_unit, line.product_uom)
               

    @api.onchange('product_id')
    def onchange_product_id(self):
        if not self.product_id:
            return
        self._product_id_change()
        self._compute_tax_id()

    def _product_id_change(self):
        if not self.product_id:
            return
        self.product_uom = self.product_id.uom_po_id or self.product_id.uom_id
        self._compute_tax_id()

    def _compute_tax_id(self):
        for line in self:
            line = line.with_company(line.company_id)
            fpos = line.partner_id.property_account_position_id 
            taxes = line.product_id.supplier_taxes_id._filter_taxes_by_company(line.company_id)
            line.taxes_id = fpos.map_tax(taxes)

    def convert_to_gram(self, qty, uom):
        qty_gram = 0
        
        if uom.factor_inv == 1:
            qty_gram = qty * 1000
        elif uom.factor_inv < 1 and self.env.ref('uom.product_uom_gram').id != uom.id:
            qty_gram = (qty * uom.ratio) / 1000
        elif self.env.ref('uom.product_uom_gram').id == uom.id:
            qty_gram = qty
        return qty_gram


    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('purchase.gold') or 'New'
                vals['all_qty'] = vals['quantity']
        return super(PurchaseGold, self).create(vals_list)

    def write(self,vals):
        if 'quantity' in vals:
            vals['all_qty'] = vals['quantity']
        return super(PurchaseGold, self).write(vals)

   