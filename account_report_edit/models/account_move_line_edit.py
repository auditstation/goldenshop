# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from datetime import timezone, datetime, date
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class AccountMoveLineInherit(models.Model):
    _inherit = 'account.move.line'

    balance_gold = fields.Float(
        string='Balance Gold',
        aggregator='sum',
        compute='_compute_gold', store=True,
        precompute=True, )

    credit_gold = fields.Float(
        string='Credit Gold',
        aggregator='sum',
        compute='_compute_gold', store=True,
        precompute=True,
    )
    debit_gold = fields.Float(
        string='Debit Gold',
        aggregator='sum',
        compute='_compute_gold', store=True,
        precompute=True,
    )

    @api.depends('product_id', 'quantity', 'product_uom_id', 'credit', 'debit', 'balance')
    def _compute_gold(self):
        all_amount = 0
        for line in self:
            amount = 0
            if line.product_id:
                ratio = line.product_uom_id.ratio if line.product_uom_id.ratio != 0 else 1
                amount = round(line.quantity / ratio * 1000,2)
                if line.account_id.account_type in ['income','expense_direct_cost']:
                    all_amount += round(line.quantity / ratio * 1000,2)
            line.debit_gold = amount if line.credit == 0 else 0
            line.credit_gold = amount if line.debit == 0 else 0
            line.balance_gold = line.debit_gold - line.credit_gold
            if line.account_id.account_type in ['asset_receivable','liability_payable']:
                line.debit_gold = all_amount if line.credit == 0 else 0
                line.credit_gold = all_amount if line.debit == 0 else 0
                line.balance_gold = line.debit_gold - line.credit_gold
