# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from datetime import timezone, datetime, date
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class ProductTemplateInherit(models.Model):
    _inherit = 'product.template'

    is_gold = fields.Boolean(company_dependent=True, compute='_compute_is_gold',
                             inverse='_set_is_gold',
                             help="To refer to the products we deal with as buying and selling with gold values")

    @api.depends_context('company')
    @api.depends('product_variant_ids.is_gold')
    def _compute_is_gold(self):
        self._compute_template_field_from_variant_field('is_gold')

    def _set_is_gold(self):
        self._set_product_variant_field('is_gold')