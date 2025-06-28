# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError, UserError
import logging, requests, json
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from odoo.tools.float_utils import float_round

_logger = logging.getLogger(__name__)

class OpenBalanceGold(models.Model):
    _name = "open.balance.gold"

    date = fields.Datetime(default=fields.Datetime.now)
    read_only = fields.Boolean()
    open_balance = fields.Float('Open Balance (g)')
    new_balance = fields.Float()
    net_profit = fields.Monetary()
    net_profit_usd = fields.Monetary()
    new_balance_money = fields.Float()
    new_balance_money_usd = fields.Monetary()
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id.id)
    currency_usd_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.ref('base.USD').id)
    company_id = fields.Many2one('res.company', readonly=True, default=lambda self: self.env.company)

    def write(self, vals):
        vals['read_only'] = True
        return super().write(vals)

    def create_every_year(self):
        this_year = datetime.now().year
        existing_records = self.search([]).filtered(lambda r: r.date.year != this_year)
        if not existing_records:
            previous_year_record = self.search([('read_only', '=', True)]).filtered(lambda r: r.date.year == this_year - 1)
            opening_balance = previous_year_record[0].new_balance if previous_year_record else 0.0
            profit_data = self._get_net_profit()
            usd_price = self._fetch_gold_price()
            intial_balance = self._convert_usd_to_company_currency(usd_price)

            self.sudo().create({
                'open_balance': opening_balance,
                'date': fields.Datetime.now(),
                'net_profit': profit_data['net_profit'],
                'net_profit_usd': profit_data['net_profit_usd'],
                'new_balance': opening_balance + profit_data['net_profit'],
                'new_balance_money': intial_balance,
                'new_balance_money_usd': usd_price,
                'read_only': True,
            })

    def get_data(self):
        data = []
        for rec in self.search([('read_only', '=', True)]):
            data.append({
                'opening_balance': rec.open_balance,
                'date': rec.date + timedelta(hours=3),
                'net_profit': rec.net_profit,
                'net_profit_usd': rec.net_profit_usd,
                'new_balance': rec.open_balance + rec.net_profit,
                'new_balance_money': float_round(rec.new_balance_money, 3),
                'new_balance_money_usd': float_round(rec.new_balance_money_usd, 3),
            })

        previous_rec = self.search([('read_only', '=', True)], limit=1)
        opening_balance = previous_rec._get_new_balance(previous_rec.net_profit, previous_rec.open_balance) if previous_rec else 0.0

        profit_data = self._get_net_profit()
        usd_price = self._fetch_gold_price()
        intial_balance = self._convert_usd_to_company_currency(usd_price)

        data.append({
            'opening_balance': opening_balance,
            'date': datetime.now() + timedelta(hours=3),
            'net_profit': profit_data['net_profit_only'],
            'net_profit_usd': profit_data['net_profit_usd_only'],
            'new_balance': opening_balance + profit_data['net_profit'],
            'new_balance_money': float_round(intial_balance, 3),
            'new_balance_money_usd': float_round(usd_price, 3),
        })

        return data

    def create_and_update(self):
        return self.env.ref('gold_dropship.action_report_open_balance').report_action(
            self, data={'model': 'open.balance.gold', 'data': self.get_data()}
        )

    def _get_net_profit(self, date=None):
        matched_value = matched_value_usd = 0.0
        net_profit = net_profit_usd = 0.0
        my_date = date or datetime.now()

        report = self.env.ref('account_reports.profit_and_loss')
        if not report:
            raise UserError(_("The financial report could not be found."))

        options = report.get_options({})
        options['date'] = {
            'date_from': datetime(my_date.year, 1, 1).date(),
            'date_to': datetime(my_date.year, 12, 31).date(),
            'mode': 'range'
        }
        options['unfold_all'] = True

        lines = report._get_lines(options)
        for line in lines:
            if line.get('name') == 'Net Profit':
                for column in line.get('columns', []):
                    if column.get('expression_label') == 'balance':
                        matched_value = column.get('no_format')
                        usd_price = self._fetch_gold_price()
                        company_currency = self.env.company.currency_id
                        usd_currency = self.env.ref('base.USD')

                        iqd_value = usd_currency._convert(usd_price, company_currency, self.env.company, fields.Date.today())
                        net_profit = matched_value / iqd_value
                        matched_value_usd = company_currency._convert(matched_value, usd_currency, self.env.company, fields.Date.today())
                        net_profit_usd = matched_value_usd / usd_price

        return {
            'net_profit': net_profit,
            'net_profit_usd': net_profit_usd,
            'net_profit_only': matched_value,
            'net_profit_usd_only': matched_value_usd
        }

    def _fetch_gold_price(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('report.url') or self.env[
            'ir.config_parameter'].sudo().get_param('web.base.url')
        url = base_url + '/gold_dropship/api/get_price'
        headers = {"Content-Type": "application/json", "Accept": "application/json",
                   "Catch-Control": "no-cache", }
        create_request_get_data = requests.get(url, data=json.dumps({}), headers=headers)
        response_body_data = json.loads(create_request_get_data.content)['result']             
        return response_body_data / 31.1035

    def _convert_usd_to_company_currency(self, usd_value):
        usd_currency = self.env.ref('base.USD')
        return usd_currency._convert(usd_value, self.env.company.currency_id, self.env.company, fields.Date.today())

    def _get_new_balance(self, net_profit, opening_balance):
        return net_profit + opening_balance

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'open.balance.gold',
            'docs': docs,
        }
