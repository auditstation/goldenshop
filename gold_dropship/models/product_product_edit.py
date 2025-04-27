# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from datetime import timezone, datetime, date
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class ProductInherit(models.Model):
    _inherit = 'product.product'

    is_gold = fields.Boolean(company_dependent=True,
                             help="To refer to the products we deal with as buying and selling with gold values")
    broken_gold = fields.Boolean(company_dependent=True)