# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from datetime import timezone, datetime, date
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class StockPickingInherit(models.Model):
    _inherit = "stock.picking"

    def button_validate(self):
        res = super().button_validate()
        if self.sale_id and self.sale_id.po_id and self.sale_id.po_id.picking_ids.mapped('state') != 'done' and not self.purchase_id:
            self.sale_id.po_id.picking_ids.button_validate()
        return res