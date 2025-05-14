# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools import float_round


class MrpRoutingWorkcenter(models.Model):
    _inherit = 'mrp.routing.workcenter'

    @api.depends('time_cycle_manual', 'time_mode', 'workorder_ids')
    def _compute_time_cycle(self):
        manual_ops = self.filtered(lambda operation: operation.time_mode == 'manual')
        for operation in manual_ops:
            operation.time_cycle = operation.time_cycle_manual
        for operation in self - manual_ops:
            data = self.env['mrp.workorder'].search([
                ('operation_id', 'in', operation.ids),
                ('qty_produced', '>', 0),
                ('state', '=', 'done')],
                order="date_finished desc, id desc")
            total_duration = 0 
            cycle_number = 0  
            for item in data:
                total_duration += item['duration']
                capacity = item['workcenter_id']._get_capacity(item.product_id)
                qty_produced = item.product_uom_id._compute_quantity(item['qty_produced'], item.product_id.uom_id)
                cycle_number += float_round((qty_produced / capacity or 1.0), precision_digits=0, rounding_method='UP')
            if cycle_number:
                operation.time_cycle = total_duration / cycle_number
            else:
                operation.time_cycle = operation.time_cycle_manual
            operation.time_cycle = operation.time_cycle_manual