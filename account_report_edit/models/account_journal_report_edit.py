# Part of Odoo. See LICENSE file for full copyright and licensing details.
import io
import datetime

from PIL import ImageFont
from markupsafe import Markup

from odoo import models, _
from odoo.tools import SQL
from odoo.tools.misc import xlsxwriter, file_path
from collections import defaultdict


class JournalReportCustomHandlerInherit(models.AbstractModel):
    _inherit = 'account.journal.report.handler'
    # def _get_custom_display_config(self):
    #     result = super()._get_custom_display_config()
    #     result['templates']['AccountReportFilters'] = 'account_report_edit.ExtendedAccountReportFilters'
    #     return result
    def _report_custom_engine_journal_report(self, expressions, options, date_scope, current_groupby, next_groupby,
                                             offset=0, limit=None, warnings=None):

        def build_result_dict(current_groupby, query_line):
            """
            Creates a line entry used by the custom engine
            """
            if current_groupby == 'account_id':
                code = query_line['account_code'][0]
            elif current_groupby == 'journal_id':
                code = query_line['journal_code'][0]
            else:
                code = None

            result_line_dict = {
                'code': code,
                'credit': query_line['credit'],
                'debit': query_line['debit'],
                'balance': query_line['balance'] if current_groupby == 'account_id' else None,
                'credit_gold': query_line['credit_gold'],
                'debit_gold': query_line['debit_gold'],
                'balance_gold': query_line['balance_gold'] if current_groupby == 'account_id' else None,
            }
            return query_line['grouping_key'], result_line_dict

        report = self.env['account.report'].browse(options['report_id'])
        report._check_groupby_fields(
            (next_groupby.split(',') if next_groupby else []) + ([current_groupby] if current_groupby else []))

        # If it is the first line, we want to render our column label
        # Since we don't use the one from the base report
        if not current_groupby:
            return {
                'code': None,
                'debit': None,
                'credit': None,
                'balance': None,
                'debit_gold': None,
                'credit_gold': None,
                'balance_gold': None
            }

        query = report._get_report_query(options, 'strict_range')
        account_alias = query.join(lhs_alias='account_move_line', lhs_column='account_id', rhs_table='account_account',
                                   rhs_column='id', link='account_id')
        account_code = self.env['account.account']._field_to_sql(account_alias, 'code', query)

        groupby_clause = SQL.identifier('account_move_line', current_groupby)
        select_from_groupby = SQL('%s AS grouping_key', groupby_clause)

        query = SQL(
            """
                SELECT
                    %(select_from_groupby)s,
                    ARRAY_AGG(DISTINCT %(account_code)s) AS account_code,
                    ARRAY_AGG(DISTINCT j.code) AS journal_code,
                    SUM("account_move_line".debit) AS debit,
                    SUM("account_move_line".credit) AS credit,
                    SUM("account_move_line".balance) AS balance,
                    SUM("account_move_line".debit_gold) AS debit_gold,
                    SUM("account_move_line".credit_gold) AS credit_gold,
                    SUM("account_move_line".balance_gold) AS balance_gold
                FROM %(table)s
                JOIN account_move am ON am.id = account_move_line.move_id
                JOIN account_journal j ON j.id = am.journal_id
                JOIN res_company cp ON cp.id = am.company_id
                WHERE %(case_statement)s AND %(search_conditions)s
                GROUP BY %(groupby_clause)s
                ORDER BY %(groupby_clause)s
            """,
            select_from_groupby=select_from_groupby,
            account_code=account_code,
            table=query.from_clause,
            search_conditions=query.where_clause,
            case_statement=self._get_payment_lines_filter_case_statement(options),
            groupby_clause=groupby_clause
        )
        self._cr.execute(query)
        query_lines = self._cr.dictfetchall()
        result_lines = []

        for query_line in query_lines:
            result_lines.append(build_result_dict(current_groupby, query_line))

        return result_lines

    def _generate_document_data_for_export(self, report, options, export_type='pdf'):
        """
        Used to generate all the data needed for the rendering of the export

        :param export_type:     The export type the generation need to use can be ('pdf' or 'xslx')

        :return: a dictionnary containing a list of all lines grouped by journals and a dictionnay with the global tax summary lines
        - journals_vals (mandatory):                    List of dictionary containing all the lines, columns, and tax summaries
            - lines (mandatory):                        A list of dict containing all tha data for each lines in format returned by _get_lines_for_journal
            - columns (mandatory):                      A list of columns for this journal returned in the format returned by _get_columns_for_journal
            - tax_summary (optional):                   A dict of data for the tax summaries inside journals in the format returned by _get_tax_summary_section
        - global_tax_summary:                           A dict with the global tax summaries data in the format returned by _get_tax_summary_section
        """
        # Ensure that all the data is synchronized with the database before we read it
        self.env.flush_all()
        query = report._get_report_query(options, 'strict_range')
        account_alias = query.join(lhs_alias='account_move_line', lhs_column='account_id', rhs_table='account_account',
                                   rhs_column='id', link='account_id')
        account_code = self.env['account.account']._field_to_sql(account_alias, 'code', query)
        account_name = self.env['account.account']._field_to_sql(account_alias, 'name')

        query = SQL(
            """
            SELECT
                account_move_line.id AS move_line_id,
                account_move_line.name,
                account_move_line.date,
                account_move_line.invoice_date,
                account_move_line.amount_currency,
                account_move_line.tax_base_amount,
                account_move_line.currency_id AS move_line_currency,
                am.id AS move_id,
                am.name AS move_name,
                am.journal_id,
                am.currency_id AS move_currency,
                am.amount_total_in_currency_signed AS amount_currency_total,
                am.currency_id != cp.currency_id AS is_multicurrency,
                p.name AS partner_name,
                %(account_code)s AS account_code,
                %(account_name)s AS account_name,
                %(account_alias)s.account_type AS account_type,
                COALESCE(account_move_line.debit, 0) AS debit,
                COALESCE(account_move_line.credit, 0) AS credit,
                COALESCE(account_move_line.balance, 0) AS balance,
                COALESCE(account_move_line.debit_gold, 0) AS debit_gold,
                COALESCE(account_move_line.credit_gold, 0) AS credit_gold,
                COALESCE(account_move_line.balance_gold, 0) AS balance_gold,
                %(j_name)s AS journal_name,
                j.code AS journal_code,
                j.type AS journal_type,
                cp.currency_id AS company_currency,
                CASE WHEN j.type = 'sale' THEN am.payment_reference WHEN j.type = 'purchase' THEN am.ref END AS reference,
                array_remove(array_agg(DISTINCT %(tax_name)s), NULL) AS taxes,
                array_remove(array_agg(DISTINCT %(tag_name)s), NULL) AS tax_grids
            FROM %(table)s
            JOIN account_move am ON am.id = account_move_line.move_id
            LEFT JOIN res_partner p ON p.id = account_move_line.partner_id
            JOIN account_journal j ON j.id = am.journal_id
            JOIN res_company cp ON cp.id = am.company_id
            LEFT JOIN account_move_line_account_tax_rel aml_at_rel ON aml_at_rel.account_move_line_id = account_move_line.id
            LEFT JOIN account_tax parent_tax ON parent_tax.id = aml_at_rel.account_tax_id and parent_tax.amount_type = 'group'
            LEFT JOIN account_tax_filiation_rel tax_filiation_rel ON tax_filiation_rel.parent_tax = parent_tax.id
            LEFT JOIN account_tax tax ON (tax.id = aml_at_rel.account_tax_id and tax.amount_type != 'group') or tax.id = tax_filiation_rel.child_tax
            LEFT JOIN account_account_tag_account_move_line_rel tag_rel ON tag_rel.account_move_line_id = account_move_line.id
            LEFT JOIN account_account_tag tag ON tag_rel.account_account_tag_id = tag.id
            LEFT JOIN res_currency journal_curr ON journal_curr.id = j.currency_id
            WHERE %(case_statement)s AND %(search_conditions)s
            GROUP BY "account_move_line".id, am.id, p.id, %(account_alias)s.id, j.id, cp.id, journal_curr.id, account_code, account_name
            ORDER BY
                CASE j.type
                    WHEN 'sale' THEN 1
                    WHEN 'purchase' THEN 2
                    WHEN 'general' THEN 3
                    WHEN 'bank' THEN 4
                    ELSE 5
                END,
                j.sequence,
                CASE WHEN am.name = '/' THEN 1 ELSE 0 END, am.date, am.name,
                CASE %(account_alias)s.account_type
                    WHEN 'liability_payable' THEN 1
                    WHEN 'asset_receivable' THEN 1
                    WHEN 'liability_credit_card' THEN 5
                    WHEN 'asset_cash' THEN 5
                    ELSE 2
                END,
                account_move_line.tax_line_id NULLS FIRST
            """,
            table=query.from_clause,
            case_statement=self._get_payment_lines_filter_case_statement(options),
            search_conditions=query.where_clause,
            account_code=account_code,
            account_name=account_name,
            account_alias=SQL.identifier(account_alias),
            j_name=self.env['account.journal']._field_to_sql('j', 'name'),
            tax_name=self.env['account.tax']._field_to_sql('tax', 'name'),
            tag_name=self.env['account.account.tag']._field_to_sql('tag', 'name')
        )

        self._cr.execute(query)
        result = {}

        # Grouping by journal_id then move_id
        for entry in self._cr.dictfetchall():
            result.setdefault(entry['journal_id'], {})
            result[entry['journal_id']].setdefault(entry['move_id'], [])
            result[entry['journal_id']][entry['move_id']].append(entry)

        journals_vals = []
        any_journal_group_has_taxes = False

        for journal_entry_dict in result.values():
            account_move_vals_list = list(journal_entry_dict.values())
            journal_vals = {
                'id': account_move_vals_list[0][0]['journal_id'],
                'name': account_move_vals_list[0][0]['journal_name'],
                'code': account_move_vals_list[0][0]['journal_code'],
                'type': account_move_vals_list[0][0]['journal_type']
            }

            if self._section_has_tax(options, journal_vals['id']):
                journal_vals['tax_summary'] = self._get_tax_summary_section(options, journal_vals)
                any_journal_group_has_taxes = True

            journal_vals['lines'] = self._get_export_lines_for_journal(report, options, export_type, journal_vals,
                                                                       account_move_vals_list)
            journal_vals['columns'] = self._get_columns_for_journal(journal_vals, export_type)
            journals_vals.append(journal_vals)

        return {
            'journals_vals': journals_vals,
            'global_tax_summary': self._get_tax_summary_section(options) if any_journal_group_has_taxes else False
        }

    def _get_columns_for_journal(self, journal, export_type='pdf'):
        """
        Creates a columns list that will be used in this journal for the pdf report

        :return: A list of the columns as dict each having:
            - name (mandatory):     A string that will be displayed
            - label (mandatory):    A string used to link lines with the column
            - class (optional):     A string with css classes that need to be applied to all that column
        """
        columns = [
            {'name': _('Document'), 'label': 'document'},
        ]

        # We have different columns regarding we are exporting to a PDF file or an XLSX document
        if export_type == 'pdf':
            columns.append({'name': _('Account'), 'label': 'account_label'})
        else:
            columns.extend([
                {'name': _('Account Code'), 'label': 'account_code'},
                {'name': _('Account Label'), 'label': 'account_label'}
            ])

        columns.extend([
            {'name': _('Name'), 'label': 'name'},
            {'name': _('Debit'), 'label': 'debit', 'class': 'o_right_alignment '},
            {'name': _('Credit'), 'label': 'credit', 'class': 'o_right_alignment '},
            {'name': _('Debit Gold'), 'label': 'debit_gold', 'class': 'o_right_alignment '},
            {'name': _('Credit Gold'), 'label': 'credit_gold', 'class': 'o_right_alignment '},
        ])

        if journal.get('tax_summary'):
            columns.append(
                {'name': _('Taxes'), 'label': 'taxes'},
            )
            if journal['tax_summary'].get('tax_grid_summary_lines'):
                columns.append({'name': _('Tax Grids'), 'label': 'tax_grids'})

        if journal['type'] == 'bank':
            columns.append({
                'name': _('Balance'),
                'label': 'balance',
                'class': 'o_right_alignment '
            })
            columns.append({
                'name': _('Balance Gold'),
                'label': 'balance_gold',
                'class': 'o_right_alignment '
            })

            if journal.get('multicurrency_column'):
                columns.append({
                    'name': _('Amount Currency'),
                    'label': 'amount_currency',
                    'class': 'o_right_alignment '
                })

        return columns

    def _query_bank_journal_initial_balance_gold(self, options, journal_id):
        report = self.env.ref('account_reports.journal_report')
        query = report._get_report_query(options, 'to_beginning_of_period', domain=[('journal_id', '=', journal_id)])
        query = SQL(
            """
                SELECT
                    COALESCE(SUM(account_move_line.balance_gold), 0) AS balance_gold
                FROM %(table)s
                JOIN account_journal journal ON journal.id = "account_move_line".journal_id AND account_move_line.account_id = journal.default_account_id
                WHERE %(search_conditions)s
                GROUP BY journal.id
            """,
            table=query.from_clause,
            search_conditions=query.where_clause,
        )
        self._cr.execute(query)
        result = self._cr.dictfetchall()
        init_balance = result[0]['balance_gold'] if len(result) >= 1 else 0
        return init_balance

    def _get_export_lines_for_bank_journal(self, report, options, export_type, journal_vals, account_moves_vals_list):
        """
        Bank journals are more complex and should be calculated separately from other journal types

        :return: A list of lines. Each line is a dict having:
            - 'column_label':           A dict containing the values for a cell with a key that links to the label of a column
                - data (mandatory):     The formatted cell value
                - class (optional):     Additional css classes to apply to the current cell
            - line_class (optional):    Additional css classes that applies to the entire line
        """
        lines = []

        # Initial balance
        current_balance = self._query_bank_journal_initial_balance(options, journal_vals['id'])
        lines.append({
            'name': {'data': _('Starting Balance')},
            'balance': {'data': report._format_value(options, current_balance, 'monetary')},
        })
        # Initial Gold balance
        current_balance_gold = self._query_bank_journal_initial_balance_gold(options, journal_vals['id'])
        lines.append({
            'name': {'data': _('Starting Balance')},
            'balance_gold': {'data': report._format_value(options, current_balance, 'float')},
        })

        # Debit and credit accumulators
        total_credit = 0
        total_debit = 0
        # Debit Gold and credit Gold accumulators
        total_credit_gold = 0
        total_debit_gold = 0

        for i, account_move_line_vals_list in enumerate(account_moves_vals_list):
            is_unreconciled_payment = not any(
                line for line in account_move_line_vals_list if
                line['account_type'] in ('liability_credit_card', 'asset_cash')
            )

            for j, move_line_entry_vals in enumerate(account_move_line_vals_list):
                # Do not display bank account lines for bank journals
                if move_line_entry_vals['account_type'] not in ('liability_credit_card', 'asset_cash'):
                    document = ''
                    if j == 0:
                        document = f'{move_line_entry_vals["move_name"]} ({move_line_entry_vals["date"]})'
                    line = self._get_base_line(report, options, export_type, document, move_line_entry_vals, j,
                                               i % 2 != 0, journal_vals.get('tax_summary'))

                    total_credit += move_line_entry_vals['credit']
                    total_debit += move_line_entry_vals['debit']

                    total_credit_gold += move_line_entry_vals['credit_gold']
                    total_debit_gold += move_line_entry_vals['debit_gold']

                    if not is_unreconciled_payment:
                        # We need to invert the balance since it is a bank journal
                        line_balance = -move_line_entry_vals['balance']
                        current_balance += line_balance
                        line.update({
                            'balance': {
                                'data': report._format_value(options, current_balance, 'monetary'),
                                'class': 'o_muted ' if self.env.company.currency_id.is_zero(line_balance) else ''
                            },
                        })
                        # We need to invert the balance since it is a bank journal
                        line_balance_gold = -move_line_entry_vals['balance_gold']
                        current_balance_gold += line_balance_gold
                        line.update({
                            'balance_gold': {
                                'data': report._format_value(options, current_balance, 'float'),
                                'class': 'o_muted ' if self.env.company.currency_id.is_zero(line_balance_gold) else ''
                            },
                        })

                    if self.env.user.has_group('base.group_multi_currency') and move_line_entry_vals[
                        'move_line_currency'] != move_line_entry_vals['company_currency']:
                        journal_vals['multicurrency_column'] = True
                        amount_currency = -move_line_entry_vals['amount_currency'] if not is_unreconciled_payment else \
                        move_line_entry_vals['amount_currency']
                        move_line_currency = self.env['res.currency'].browse(move_line_entry_vals['move_line_currency'])
                        line.update({
                            'amount_currency': {
                                'data': report._format_value(
                                    options,
                                    amount_currency,
                                    'monetary',
                                    format_params={'currency_id': move_line_currency.id},
                                ),
                                'class': 'o_muted ' if move_line_currency.is_zero(amount_currency) else '',
                            }
                        })
                    lines.append(line)

        # Add an empty line to add a separation between the total section and the data section
        lines.append({})

        total_line = {
            'name': {'data': _('Total')},
            'balance': {'data': report._format_value(options, current_balance, 'monetary')},
        }
        lines.append(total_line)
        total_line = {
            'name': {'data': _('Total Gold')},
            'balance_gold': {'data': report._format_value(options, current_balance_gold, 'float')},
        }
        lines.append(total_line)

        return lines

    def _get_base_line(self, report, options, export_type, document, line_entry, line_index, even, has_taxes):
        """
        Returns the generic part of a line that is used by both '_get_lines_for_journal' and '_get_lines_for_bank_journal'

        :return:                                    A dict with base values for the line
            - line_class (mandatory):                   Css classes that applies to this whole line
            - document (mandatory):                     A dict containing the cell data for the column document
                - data (mandatory):                         The value of the cell formatted
                - class (mandatory):                        css class for this cell
            - account (mandatory):                      A dict containing the cell data for the column account
                - data (mandatory):                         The value of the cell formatted
            - account_code (mandatory):                 A dict containing the cell data for the column account_code
                - data (mandatory):                         The value of the cell formatted
            - account_label (mandatory):                A dict containing the cell data for the column account_label
                - data (mandatory):                         The value of the cell formatted
            - name (mandatory):                         A dict containing the cell data for the column name
                - data (mandatory):                         The value of the cell formatted
            - debit (mandatory):                        A dict containing the cell data for the column debit
                - data (mandatory):                         The value of the cell formatted
                - class (mandatory):                        css class for this cell
            - credit (mandatory):                       A dict containing the cell data for the column credit
                - data (mandatory):                         The value of the cell formatted
                - class (mandatory):                        css class for this cell

            - taxes(optional):                          A dict containing the cell data for the column taxes
                - data (mandatory):                         The value of the cell formatted
            - tax_grids(optional):                          A dict containing the cell data for the column taxes
                - data (mandatory):                         The value of the cell formatted
        """
        company_currency = self.env.company.currency_id

        name = line_entry['name'] or line_entry['reference']
        account_label = line_entry['partner_name'] or line_entry['account_name']

        if line_entry['account_type'] not in ('asset_receivable', 'liability_payable'):
            account_label = line_entry['account_name']
        elif line_entry['partner_name'] and line_entry['account_type'] in ('asset_receivable', 'liability_payable'):
            name = f"{line_entry['partner_name']} {name or ''}"

        line = {
            'line_class': 'o_even ' if even else 'o_odd ',
            'document': {'data': document, 'class': 'o_bold ' if line_index == 0 else ''},
            'account_code': {'data': line_entry['account_code']},
            'account_label': {'data': account_label if export_type != 'pdf' else line_entry["account_code"]},
            'name': {'data': name},
            'debit': {
                'data': report._format_value(options, line_entry['debit'], 'monetary'),
                'class': 'o_muted ' if company_currency.is_zero(line_entry['debit']) else ''
            },
            'credit': {
                'data': report._format_value(options, line_entry['credit'], 'monetary'),
                'class': 'o_muted ' if company_currency.is_zero(line_entry['credit']) else ''
            },
            'debit_gold': {
                'data': report._format_value(options, line_entry['debit_gold'], 'float'),
                'class': 'o_muted ' if company_currency.is_zero(line_entry['debit_gold']) else ''
            },
            'credit_gold': {
                'data': report._format_value(options, line_entry['credit_gold'], 'float'),
                'class': 'o_muted ' if company_currency.is_zero(line_entry['credit_gold']) else ''
            },
        }

        if has_taxes:
            tax_val = ''
            if line_entry['taxes']:
                tax_val = _('T: %s', ', '.join(line_entry['taxes']))
            elif line_entry['tax_base_amount'] is not None:
                tax_val = _('B: %s', report._format_value(options, line_entry['tax_base_amount'], 'monetary'))

            line.update({
                'taxes': {'data': tax_val},
                'tax_grids': {'data': ', '.join(line_entry['tax_grids'])},
            })

        return line
