# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from datetime import timezone, datetime, date
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class ProductTemplateInherit(models.Model):
    _inherit = 'product.template'

    is_gold = fields.Boolean(company_dependent=True,store=True,
                             help="To refer to the products we deal with as buying and selling with gold values")
    broken_gold = fields.Boolean(store=True,company_dependent=True)
    