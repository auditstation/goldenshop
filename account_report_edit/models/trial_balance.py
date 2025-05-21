# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, _, fields
from odoo.tools import float_compare
from odoo.tools.misc import DEFAULT_SERVER_DATE_FORMAT


TRIAL_BALANCE_END_COLUMN_GROUP_KEY = '_trial_balance_end_column_group'


class TrialBalanceCustomHandlerInherit(models.AbstractModel):
    _inherit = 'account.trial.balance.report.handler'
   

    def _dynamic_lines_generator(self, report, options, all_column_groups_expression_totals, warnings=None):
        def _update_column(line, column_key, new_value):
            line['columns'][column_key]['no_format'] = new_value
            line['columns'][column_key]['is_zero'] = self.env.company.currency_id.is_zero(new_value)

        def _update_balance_columns(line, debit_column_key, credit_column_key,debit_gold_column_key, credit_gold_column_key, balance_column_key=None,balance_gold_column_key=None):
            debit_value = line['columns'][debit_column_key]['no_format'] if debit_column_key is not None else False
            credit_value = line['columns'][credit_column_key]['no_format'] if credit_column_key is not None else False
            debit_gold_value = line['columns'][debit_gold_column_key]['no_format'] if debit_gold_column_key is not None else False
            credit_gold_value = line['columns'][credit_gold_column_key]['no_format'] if credit_gold_column_key is not None else False

            if debit_value and credit_value:
                new_debit_value = 0.0
                new_credit_value = 0.0

                if self.env.company.currency_id.compare_amounts(debit_value, credit_value) == 1:
                    new_debit_value = debit_value - credit_value
                else:
                    new_credit_value = (debit_value - credit_value) * -1

                _update_column(line, debit_column_key, new_debit_value)
                _update_column(line, credit_column_key, new_credit_value)
            if debit_gold_value and credit_gold_value:
                new_debit_gold_value = 0.0
                new_credit_gold_value = 0.0

                if self.env.company.currency_id.compare_amounts(debit_gold_value, credit_gold_value) == 1:
                    new_debit_gold_value = debit_gold_value - credit_gold_value
                else:
                    new_credit_gold_value = (debit_gold_value - credit_gold_value) * -1

                _update_column(line, debit_gold_column_key, new_debit_gold_value)
                _update_column(line, credit_gold_column_key, new_credit_gold_value)

            if balance_column_key is not None:
                _update_column(line, balance_column_key, debit_value - credit_value)
            
            if balance_gold_column_key is not None:
                _update_column(line, balance_gold_column_key, debit_gold_value - credit_gold_value)

        lines = [line[1] for line in self.env['account.general.ledger.report.handler']._dynamic_lines_generator(report, options, all_column_groups_expression_totals, warnings=warnings)]

        # We need to find the index of debit and credit columns for initial and end balance in case of extra custom columns
        init_balance_debit_index = next((index for index, column in enumerate(options['columns']) if column.get('expression_label') == 'debit'), None)
        init_balance_credit_index = next((index for index, column in enumerate(options['columns']) if column.get('expression_label') == 'credit'), None)

        end_balance_debit_index = next((index for index, column in enumerate(options['columns']) if column.get('expression_label') == 'debit' and column.get('column_group_key') == TRIAL_BALANCE_END_COLUMN_GROUP_KEY), None)
        end_balance_credit_index = next((index for index, column in enumerate(options['columns']) if column.get('expression_label') == 'credit' and column.get('column_group_key') == TRIAL_BALANCE_END_COLUMN_GROUP_KEY), None)
        end_balance_balance_index = next((index for index, column in enumerate(options['columns']) if column.get('expression_label') == 'balance' and column.get('column_group_key') == TRIAL_BALANCE_END_COLUMN_GROUP_KEY), None)

        #### Gold
        init_balance_debit_gold_index = next((index for index, column in enumerate(options['columns']) if column.get('expression_label') == 'debit_gold'), None)
        init_balance_credit_gold_index = next((index for index, column in enumerate(options['columns']) if column.get('expression_label') == 'credit_gold'), None)

        end_balance_debit_gold_index = next((index for index, column in enumerate(options['columns']) if column.get('expression_label') == 'debit_gold' and column.get('column_group_key') == TRIAL_BALANCE_END_COLUMN_GROUP_KEY), None)
        end_balance_credit_gold_index = next((index for index, column in enumerate(options['columns']) if column.get('expression_label') == 'credit_gold' and column.get('column_group_key') == TRIAL_BALANCE_END_COLUMN_GROUP_KEY), None)
        end_balance_balance_gold_index = next((index for index, column in enumerate(options['columns']) if column.get('expression_label') == 'balance_gold' and column.get('column_group_key') == TRIAL_BALANCE_END_COLUMN_GROUP_KEY), None)

        currency = self.env.company.currency_id
        for line in lines[:-1]:
            # Initial balance
            _update_balance_columns(line, init_balance_debit_index, init_balance_credit_index,init_balance_debit_gold_index, init_balance_credit_gold_index)

            # End balance: sum all the previous columns for both debit and credit
            if end_balance_debit_index is not None:
                end_balance_debit_sum = sum(
                    currency.round(column['no_format'])
                    for index, column in enumerate(line['columns'])
                    if column.get('expression_label') == 'debit' and index != end_balance_debit_index and column['no_format'] is not None
                )
                _update_column(line, end_balance_debit_index, end_balance_debit_sum)
            ### Gold
            # End balance: sum all the previous columns for both debit and credit
            if end_balance_debit_gold_index is not None:
                end_balance_debit_gold_sum = sum(
                    currency.round(column['no_format'])
                    for index, column in enumerate(line['columns'])
                    if column.get('expression_label') == 'debit_gold' and index != end_balance_debit_gold_index and column['no_format'] is not None
                )
                _update_column(line, end_balance_debit_gold_index, end_balance_debit_gold_sum)

            if end_balance_credit_index is not None:
                end_balance_credit_sum = sum(
                    currency.round(column['no_format'])
                    for index, column in enumerate(line['columns'])
                    if column.get('expression_label') == 'credit' and index != end_balance_credit_index and column['no_format'] is not None
                )
                _update_column(line, end_balance_credit_index, end_balance_credit_sum)
            #### Gold
            if end_balance_credit_gold_index is not None:
                end_balance_credit_gold_sum = sum(
                    currency.round(column['no_format'])
                    for index, column in enumerate(line['columns'])
                    if column.get('expression_label') == 'credit_gold' and index != end_balance_credit_gold_index and column['no_format'] is not None
                )
                _update_column(line, end_balance_credit_gold_index, end_balance_credit_gold_sum)

            _update_balance_columns(line, end_balance_debit_index, end_balance_credit_index, end_balance_balance_index,end_balance_debit_gold_index, end_balance_credit_gold_index, end_balance_balance_gold_index)

            line.pop('expand_function', None)
            line.pop('groupby', None)
            line.update({
                'unfoldable': False,
                'unfolded': False,
            })

            res_model = report._get_model_info_from_id(line['id'])[0]
            if res_model == 'account.account':
                line['caret_options'] = 'trial_balance'

        # Total line
        if lines:
            total_line = lines[-1]

            for index in (init_balance_debit_index, init_balance_credit_index, end_balance_debit_index, end_balance_credit_index,init_balance_debit_gold_index, init_balance_credit_gold_index, end_balance_debit_gold_index, end_balance_credit_gold_index):
                if index is not None:
                    total_line['columns'][index]['no_format'] = sum(currency.round(line['columns'][index]['no_format']) for line in lines[:-1] if report._get_model_info_from_id(line['id'])[0] == 'account.account')
                    total_line['columns'][index]['blank_if_zero'] = False

        return [(0, line) for line in lines]

    

    
    
    