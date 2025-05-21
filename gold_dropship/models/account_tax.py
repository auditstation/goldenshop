# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, Command
import logging
_logger = logging.getLogger(__name__)

class AccountTax(models.Model):
    _inherit = 'account.tax'

    @api.model
    def _add_tax_details_in_base_line(self, base_line, company, rounding_method=None):
        price_unit_after_discount = base_line['price_unit'] * (1 - (base_line['discount'] / 100.0))
        if 'record' in base_line and base_line['record']!= None:
            if 'purchase.order.line' in str(base_line['record']) and base_line['record'].purity != 0:
                price_unit_after_discount = base_line['price_unit'] * (1 - (base_line['discount'] / 100.0)) * base_line['record'].purity   
            if 'account.move.line' in str(base_line['record']) and base_line['record'].purity != 0:
               price_unit_after_discount = base_line['price_unit'] * (1 - (base_line['discount'] / 100.0)) * base_line['record'].purity   
        taxes_computation = base_line['tax_ids']._get_tax_details(
            price_unit=price_unit_after_discount,
            quantity=base_line['quantity'],
            precision_rounding=base_line['currency_id'].rounding,
            rounding_method=rounding_method or company.tax_calculation_rounding_method,
            product=base_line['product_id'],
            special_mode=base_line['special_mode'],
        )
        rate = base_line['rate']
        tax_details = base_line['tax_details'] = {
            'raw_total_excluded_currency': taxes_computation['total_excluded'],
            'raw_total_excluded': taxes_computation['total_excluded'] / rate if rate else 0.0,
            'raw_total_included_currency': taxes_computation['total_included'],
            'raw_total_included': taxes_computation['total_included'] / rate if rate else 0.0,
            'taxes_data': [],
        }
        if company.tax_calculation_rounding_method == 'round_per_line':
            tax_details['raw_total_excluded'] = company.currency_id.round(tax_details['raw_total_excluded'])
            tax_details['raw_total_included'] = company.currency_id.round(tax_details['raw_total_included'])
        for tax_data in taxes_computation['taxes_data']:
            tax_amount = tax_data['tax_amount'] / rate if rate else 0.0
            base_amount = tax_data['base_amount'] / rate if rate else 0.0
            if company.tax_calculation_rounding_method == 'round_per_line':
                tax_amount = company.currency_id.round(tax_amount)
                base_amount = company.currency_id.round(base_amount)
            tax_details['taxes_data'].append({
                **tax_data,
                'raw_tax_amount_currency': tax_data['tax_amount'],
                'raw_tax_amount': tax_amount,
                'raw_base_amount_currency': tax_data['base_amount'],
                'raw_base_amount': base_amount,
            })
