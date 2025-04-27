# -*- coding: utf-8 -*-
import base64
import json
import logging
from datetime import datetime
import requests
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)




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

    