# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from datetime import timezone, datetime, date
from odoo.exceptions import ValidationError
from odoo.addons.account.models.account_move import TYPE_REVERSE_MAP
import logging
_logger = logging.getLogger(__name__)


class AccountMoveInherit(models.Model):
    _inherit = 'account.move'

    payment_method = fields.Selection(string='Payment Method', selection=[
        ('cash', 'Cash'),
        ('gold', 'Cash & Gold'),
    ], required=True, default='cash', readonly=True)

    related_invoice = fields.Many2one('account.move',copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        for i in res:
            order_id = i.line_ids.sale_line_ids.order_id
            
            all_received_billed = all(line.qty_received == line.qty_invoiced and line.qty_received != 0 for line in order_id.po_id.order_line)
            if order_id and order_id.po_id and i.move_type == 'out_invoice' and not all_received_billed:
                self.create_bill(order_id, i)
            if i.reversed_entry_id and i.reversed_entry_id.line_ids.sale_line_ids.order_id.payment_method in ['gold','cash'] and i.move_type == 'out_refund':
                for j in i.invoice_line_ids:
                    if j.display_type == 'line_section' and (j.name == 'Gold Sold' or j.name == 'Down Payments'):
                        j.unlink()
        return res

    def create_bill(self, order_id, invoice):
        purchase_id = order_id.po_id
        bill = purchase_id.sudo().with_context({'create_bill': True}).action_create_invoice()
        self.env['account.move'].with_user(2).browse(bill['res_id']).write({
            'related_invoice': invoice.id
        })

    def action_post(self):
        res = super().action_post()
        bill = self.sudo().search([('related_invoice', '=', self.id),('company_id','=',self.company_id.id)])
        po_id = self.line_ids.sale_line_ids.order_id.po_id
        if bill and po_id and self.move_type == 'out_invoice':
            if bill.state == 'draft':
                bill.invoice_date = fields.Date.today()
                bill.sudo().action_post()
        return res
        
    def button_draft(self):
        res = super().button_draft()
        bill = self.sudo().search([('related_invoice', '=', self.id),('company_id','=',self.company_id.id)])
        po_id = self.line_ids.sale_line_ids.order_id.po_id
        if bill and po_id and self.move_type == 'out_invoice':
            if bill.state == 'posted':
                bill.sudo().button_draft()
        return res
    
    def button_cancel(self):
        res = super().button_cancel()
        bill = self.sudo().search([('related_invoice', '=', self.id),('company_id','=',self.company_id.id)])
        po_id = self.line_ids.sale_line_ids.order_id.po_id
        if bill and po_id and self.move_type == 'out_invoice':
            if bill.state == 'draft':
                bill.sudo().button_cancel()
        return res


    def _reverse_moves(self, default_values_list=None, cancel=False):
        if not default_values_list:
            default_values_list = [{} for move in self]
        if cancel:
            lines = self.mapped('line_ids')
            if lines:
                lines.remove_move_reconcile()
        reverse_moves = self.env['account.move']
        for move, default_values in zip(self, default_values_list):
            default_values.update({
                'move_type': TYPE_REVERSE_MAP[move.move_type],
                'reversed_entry_id': move.id,
                'partner_id': move.partner_id.id,
            })
            reverse_moves += move.with_context(
                move_reverse_cancel=cancel,
                include_business_fields=True,
                skip_invoice_sync=move.move_type == 'entry',
            ).copy(default_values)
        if reverse_moves.reversed_entry_id.line_ids.sale_line_ids.order_id.payment_method in ['gold','cash']:
            for i in reverse_moves.invoice_line_ids:
                if i.product_id.broken_gold or i.is_downpayment:
                    i.unlink()
        reverse_moves.with_context(skip_invoice_sync=cancel).write({'line_ids': [
            Command.update(line.id, {
                'balance': -line.balance,
                'amount_currency': -line.amount_currency,
            })
            for line in reverse_moves.line_ids
            if line.move_id.move_type == 'entry' or line.display_type == 'cogs'
        ]})
        if cancel:
            reverse_moves.with_context(move_reverse_cancel=cancel)._post(soft=False)

        return reverse_moves

  
