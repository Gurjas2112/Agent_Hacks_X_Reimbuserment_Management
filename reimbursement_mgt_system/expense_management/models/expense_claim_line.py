# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ExpenseClaimLine(models.Model):
    _name = 'expense.claim.line'
    _description = 'Expense Claim Line Item'
    _order = 'sequence, id'

    claim_id = fields.Many2one(
        'expense.claim', string='Expense Claim',
        required=True, ondelete='cascade'
    )
    sequence = fields.Integer(string='Sequence', default=10)
    name = fields.Char(string='Item Description', required=True)
    quantity = fields.Float(string='Quantity', default=1.0, digits=(16, 2))
    unit_price = fields.Float(string='Unit Price', digits=(16, 2))
    total_price = fields.Float(
        string='Total Price', compute='_compute_total_price',
        store=True, digits=(16, 2)
    )

    @api.depends('quantity', 'unit_price')
    def _compute_total_price(self):
        for line in self:
            line.total_price = line.quantity * line.unit_price
