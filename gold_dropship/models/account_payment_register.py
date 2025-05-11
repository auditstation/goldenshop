# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
import logging
_logger = logging.getLogger(__name__)


class AccountRegisterInherit(models.TransientModel):
    _inherit = 'account.payment.register'

    def _create_payments(self):
        original_move = self.env['account.move'].search([('line_ids', 'in', self.line_ids.ids)]).filtered(lambda l: l.company_id.id == self.company_id.id)
        bill_move = self.env['account.move'].sudo().search([('related_invoice', '=', original_move.id),('company_id','=',self.company_id.id)])
        amount_paid = bill_move.amount_residual if self.amount >= bill_move.amount_residual else self.amount
        if bill_move:
            vals = self.env['account.payment.register'].with_context(active_model='account.move',
                                                                     active_ids=bill_move.ids).sudo().create({
                'amount': amount_paid,
                'communication': bill_move.name,
                'journal_id': self.journal_id.id,
                'company_id': self.company_id.id,
                'currency_id': self.currency_id.id,
                'partner_id': self.partner_id.id

            }).sudo()
            vals._create_payments()
        return super()._create_payments()

  
