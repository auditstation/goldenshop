# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from datetime import timezone, datetime, date
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class AccountMoveInherit(models.Model):
    _inherit = 'account.move'

    payment_method = fields.Selection(string='Payment Method', selection=[
        ('cash', 'Cash'),
        ('gold', 'Cash & Gold'),
    ], required=True, default='cash', readonly=True)

    