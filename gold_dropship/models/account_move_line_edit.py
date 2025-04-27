# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from datetime import timezone, datetime, date
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class AccountMoveLineInherit(models.Model):
    _inherit = 'account.move.line'

    purity = fields.Float(string='Purity')
    pure_gold = fields.Float(string='Pure Gold', compute='_compute_pure_gold')

    @api.depends('quantity', 'purity')
    def _compute_pure_gold(self):
        for rec in self:
            rec.pure_gold = rec.quantity * rec.purity
     
    
    @api.depends('quantity', 'discount', 'price_unit', 'tax_ids', 'currency_id','purity','pure_gold')
    def _compute_totals(self):
        """ Compute 'price_subtotal' / 'price_total' outside of `_sync_tax_lines` because those values must be visible for the
        user on the UI with draft moves and the dynamic lines are synchronized only when saving the record.
        """
        AccountTax = self.env['account.tax']
        for line in self:
            # TODO remove the need of cogs lines to have a price_subtotal/price_total
            if line.display_type not in ('product', 'cogs'):
                line.price_total = line.price_subtotal = False
                continue

            base_line = line.move_id._prepare_product_base_line_for_taxes_computation(line)
            AccountTax._add_tax_details_in_base_line(base_line, line.company_id)
            line.price_subtotal = base_line['tax_details']['raw_total_excluded_currency']
            line.price_total = base_line['tax_details']['raw_total_included_currency']

    
     
    def write(self,vals):
        res = super().write(vals)
        if 'purity' in vals and vals['purity'] and not self.env.context.get('no_need_edit'):
            self.purchase_line_id.purity = vals['purity']
        return res