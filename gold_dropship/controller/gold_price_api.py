# -*- coding: utf-8 -*-
import base64
import json
import logging
from datetime import datetime
import requests
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)
from odoo.http import request
import io
import xlsxwriter

class GoldReportExcelController(http.Controller):
    @http.route('/gold/report/excel', type='http', auth='user')
    def gold_report_excel(self):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet()

        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#AF9237',
            'border': 1,
            'font_color': '#FFFFFF',
            'align': 'center',
            'valign': 'vcenter',
        })
        money_format = workbook.add_format({
        'num_format': '$#,##0.00',
        'border': 1,
        })
        money_format_2 = workbook.add_format({
        'num_format': 'IQD#,##0.00',
        'border': 1,
        })
    
        text_format = workbook.add_format({
            'border': 1,
        })
        date_format = workbook.add_format({
            'num_format': 'dd/mm/yyyy hh:mm:ss',  # or 'yyyy-mm-dd', etc.
           
            'align': 'center',
            'valign': 'vcenter',
        })
        worksheet.write(0, 0, 'DATE',header_format)
        worksheet.set_column(0, 0, 20)
        worksheet.write(0, 1, 'Opening balance',header_format)
        worksheet.set_column(0, 1, 20)
        worksheet.write(0, 2, 'NET PROFIT IQD',header_format)
        worksheet.set_column(0, 2, 40)
        worksheet.write(0, 3, 'NET PROFIT USD',header_format)
        worksheet.set_column(0, 3, 20)
        # worksheet.write(0, 4, 'Open Balance Money IQD',header_format)
        # worksheet.set_column(0, 4, 200)
        # worksheet.write(0, 5, 'Open Balance Money USD',header_format)
        # worksheet.set_column(0, 5, 200)
        worksheet.write(0, 4, 'New balance',header_format)
        worksheet.set_column(0, 4, 20)

        # Example data, you'd replace this with real data
        data = request.env['open.balance.gold'].get_data()
        row = 1
        for line in data:
            worksheet.write(row, 0, line.get('date', ''),date_format)
            worksheet.write(row, 1, line.get('opening_balance', 0))
            worksheet.write(row, 2, line.get('net_profit', 0))
            worksheet.write(row, 3, line.get('net_profit_usd', 0))
            # worksheet.write(row, 4, line.get('new_balance_money', 0))
            # worksheet.write(row, 5, line.get('new_balance_money_usd', 0))
            worksheet.write(row, 6, line.get('new_balance', 0))
            row += 1

        workbook.close()
        output.seek(0)

        return request.make_response(
            output.read(),
            headers=[
                ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                ('Content-Disposition', 'attachment; filename=gold_report.xlsx')
            ]
        )



class GoldPriceController(http.Controller):
    
    @http.route('/gold_dropship/api/get_price', type='json', auth="none")
    def make_gapi_request(self):
        # api_key = "goldapi-4bipfysm77e2gr1-io"
        # symbol = "XAU"
        # curr = "USD"
        # date = ""

        # url = f"https://www.goldapi.io/api/{symbol}/{curr}{date}"
        url = f"https://api.gold-api.com/price/XAU"
        headers = {
            # "x-access-token": api_key,
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            # result = response.text
            res = json.loads(response.content)
            return res.get('price')
        except requests.exceptions.RequestException as e:
            _logger.info('there is a wrong with connection{}'.format(str(e)))

    