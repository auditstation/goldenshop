# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import ast
import base64
import datetime
import io
import json
import logging
import re
from ast import literal_eval
from collections import defaultdict
from functools import cmp_to_key
from itertools import groupby

import markupsafe
from dateutil.relativedelta import relativedelta
from PIL import ImageFont

from odoo import models, fields, api, _, osv
from odoo.addons.web.controllers.utils import clean_action
from odoo.exceptions import RedirectWarning, UserError, ValidationError
from odoo.models import check_method_name
from odoo.tools import date_utils, get_lang, float_is_zero, float_repr, SQL, parse_version, Query
from odoo.tools.float_utils import float_round, float_compare
from odoo.tools.misc import file_path, format_date, formatLang, split_every, xlsxwriter
from odoo.tools.safe_eval import expr_eval, safe_eval

_logger = logging.getLogger(__name__)


class AccountReportInherit(models.Model):
    _inherit = 'account.report'

    filter_uom = fields.Boolean(
        string="UOM Filter",
        compute=lambda x: x._compute_report_option_filter('filter_uom'), readonly=False, store=True,
        depends=['root_report_id', 'section_main_report_ids'],
    )

    
    def _init_options_uom(self, options, previous_options=None):
        if not self.filter_uom:
            return

        previous_uom = (previous_options or {}).get('product_uom_id', [])
        product_uom_ids = [int(x) for x in previous_uom]
        selected_uom = self.env['uom.uom'].with_context(active_test=False).search(
            [('id', 'in', product_uom_ids)])

        options['display_uom'] = True
        options['product_uom_id'] = selected_uom.ids
        options['selected_uom_names'] = selected_uom.mapped('name')

    @api.model
    def _get_options_uom_domain(self, options):
        domain = []

        if options.get('product_uom_id'):
            product_uom_ids = [int(uom) for uom in options['product_uom_id']]
            domain.append(('product_uom_id', 'in', product_uom_ids))
        return domain


    def _get_options_domain(self, options, date_scope):
        domain = super()._get_options_domain(options, date_scope)
        domain += self._get_options_uom_domain(options)
        return domain


# class AccountHandelerCustomHandlerInherit(models.AbstractModel):
#     _inherit = 'account.report.custom.handler'

#     def _get_custom_display_config(self):
#             return {
#                 'templates': {
#                     'AccountReportFilters': 'account_report_edit.ExtendedAccountReportFilters',
#                 },
#             }