# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging
import requests
import json
import re
import ast
_logger = logging.getLogger(__name__)

class GoldOpenWizard(models.Model):
    _name = 'gold.open'
    selected = fields.Boolean()
    po_id = fields.Many2one('purchase.order')
    sequence = fields.Char()
    product_id = fields.Many2one('product.product')
    qty = fields.Float(string='Quantity')
    product_uom = fields.Many2one('uom.uom', string='Unit of Measure')
    quantity_purchase = fields.Float(compute="_compute_quantity_purchase",store=True)   
    requested_qty = fields.Float(string='Requested Quantity')
    gold_id = fields.Many2one('purchase.gold')
    partner_id = fields.Many2one('res.partner')
    line_id = fields.Many2one('gold.wizard')
    
    @api.depends('qty','product_uom')
    def _compute_quantity_purchase(self):
        for rec in self:
            rec.quantity_purchase =self.convert_to_gram(rec.qty,rec.product_uom)
    
    
    @api.onchange('requested_qty')
    def change_requested_qty(self):
        if self.requested_qty and self.requested_qty > self.convert_to_gram(self.qty,self.product_uom):
            raise UserError('You have requested quantities higher than the quantity avaliable.')
            

    def convert_to_gram(self, qty, uom):
        qty_gram = 0
        
        if uom.factor_inv == 1:
            qty_gram = qty * 1000
        elif uom.factor_inv < 1 and self.env.ref('uom.product_uom_gram').id != uom.id:
            qty_gram = (qty * uom.ratio) / 1000
        elif self.env.ref('uom.product_uom_gram').id == uom.id:
            qty_gram = qty
        return qty_gram
   
 

class GoldInfoWizard(models.Model):
    _name = 'gold.wizard'
    _description = 'Customize the information to influence the gold model.'
    
    product_lines = fields.One2many('gold.open','line_id')
    name_product = fields.Char(readonly=True)
    
    
    def confirm(self):
        try:
            requested_qty = sum(self.mapped('product_lines').filtered(lambda l:l.selected).mapped('requested_qty'))
            
            pol = self.env['purchase.order.line'].browse(int(self.env.context.get('active_line')))
            # record = self.browse(ast.literal_eval(str(self.env.context.get('active_open')))).filtered(lambda l:l.selected)
            val = {'gold_ids':self.mapped('product_lines').filtered(lambda l:l.selected).mapped('gold_id'),
                   'qty_check':True,
                   'requested_qty':requested_qty}
            pol.sudo().write(val)
            
            for i in self.mapped('product_lines').filtered(lambda l:l.selected):
                record=self.env['purchase.gold.info'].sudo().create({
                    'gold_id':i.gold_id.id,
                    'po_line':pol.id,
                    'qty':i.requested_qty,
                  
                })
                record.gold_id.po_gold_line=[(4,record.id)]
            if self.env.context.get('last_one'):
                pol.order_id.with_context({'last_confirm':True}).button_confirm()
                return True
            return pol.order_id.with_context({'last_confirm':False}).button_confirm()
            
        except UserError as e:
            raise UserError(e.message)
        
    
    @api.onchange('product_lines')
    def _onchange_requested_qty(self):
        total_wiz = 0
        for rec in self.product_lines:
            # list_ids = ast.literal_eval(str(self.env.context.get('active_open'))) 
            # total_wiz += rec.convert_to_gram(rec.requested_qty,rec.product_uom) 
            total_wiz += rec.requested_qty
            total_in_line = sum(rec.convert_to_gram(i.product_qty, i.product_uom) for i in rec.env['purchase.order.line'].browse(int(self.env.context.get('active_line'))))
            if total_wiz > total_in_line:
                warning_mess = {
                    'title': _('Ordered quantity invalid!'),
                    'message': _('You have requested quantities higher than the permitted limit in your purchase order.'),
                    }
                return {'warning': warning_mess}
               
            
        

  
    
    
