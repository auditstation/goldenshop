# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from datetime import timezone, datetime, date
from odoo.exceptions import ValidationError
import logging
import requests
import json
import re
_logger = logging.getLogger(__name__)


class PurchaseOrderInherit(models.Model):
    _inherit = "purchase.order"

    count_pure = fields.Float(compute="_compute_pure")

    def _compute_pure(self):
        for rec in self:
             rec.count_pure = len([j.id for i in rec.order_line for j in i.gold_ids])
        

    @api.onchange('currency_id')
    def change_price(self):
        for rec in self.order_line:
            rec._compute_price_unit_and_date_planned_and_name()

    def create_wiz(self, active_line):
        records = []
        line_ids=[]
        vals = {
            'name_product':f"Please select pure gold for this product {active_line.name}, quantity :{active_line.product_qty}{active_line.product_uom.name}",
            'product_lines':[(0,0,{
            'sequence':rec.name,
            'po_id':self.id,
            'product_id':rec.product_id.id,
            'qty':rec.quantity,
            'gold_id':rec.id,
                'partner_id':rec.partner_id.id,
            'product_uom':rec.product_uom.id,    
        })for rec in self.env['purchase.gold'].sudo().search([('state','=','available')])]
        }
        
        records.append(self.env['gold.wizard'].sudo().create(vals))
        return records
    
    def check_line_update(self):
        true_line = self.mapped('order_line').filtered(lambda l:not l.qty_check and l.product_id.is_gold)
        active_line = true_line[0] if true_line else False
        state = True if len(true_line) != 0 else False
        return {'state':state,'active_line':active_line,'len_line':len(true_line),'true_line':true_line}
     
    def open_related_wiz(self,active_line,last_one):
        records = self.create_wiz(active_line)
        return {
            'type': 'ir.actions.act_window',
            'name': 'Gold Purchase Information',
            'res_model': 'gold.wizard',
            'view_mode': 'form',
            'res_id':records[0].id,
            'target': 'new',
            'context': {
                'active_id': self.id,
                'active_model': 'purchase.order',
                'default_po_id': self.id,
                'active_open':records,
                'active_line':active_line.id,
                'last_one':last_one,
            }
        }


    def button_confirm(self):
        for rec in self:
            line = rec.check_line_update()
            if line.get('state') and not self.env.context.get('last_confirm'):
                return rec.open_related_wiz(active_line=line.get('active_line'),last_one=True if line.get('len_line') == 1 else False)
            else:
                return super().button_confirm()
    
    def action_view_related_pure_gold(self):
        all_ids = [j.id for i in self.order_line for j in i.gold_ids]
        view_id = self.env.ref('gold_dropship.view_custom_order_line_move_tree')
        return {
            'name': 'Related Pure gold stock',
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.gold',
            'view_mode': 'list,form',
            'views': [(view_id.id, 'list'), (False, 'form')],
            'domain': [('id', 'in',all_ids)],
           
        }

    def button_cancel(self):
        for rec in self:
            for i in rec.order_line.mapped('gold_ids').mapped('po_gold_line').filtered(lambda l:l.po_line.order_id.id == rec.id):
                i.unlink()
            for l in rec.order_line.mapped('gold_ids'):
                l._compute_transfer_qty()
                l._compute_qty()
                l._compute_all_qty_g()
                rec.order_line.write({
                            'gold_ids': [(3, l.id)]
                        })
        
            return super().button_cancel()
                
                
            