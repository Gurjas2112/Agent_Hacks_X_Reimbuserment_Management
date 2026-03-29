# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ExpensePolicy(models.Model):
    _name = 'expense.policy'
    _description = 'Expense Policy Rule'
    _order = 'company_id, category'

    name = fields.Char(
        string='Policy Name', required=True,
        help='Descriptive name for this policy rule.'
    )
    company_id = fields.Many2one(
        'expense.company', string='Company', required=True,
        help='Company this policy applies to.'
    )
    category = fields.Selection([
        ('all', 'All Categories'),
        ('travel', 'Travel'),
        ('meals', 'Meals'),
        ('accommodation', 'Accommodation'),
        ('transport', 'Transport'),
        ('office_supplies', 'Office Supplies'),
        ('training', 'Training'),
        ('medical', 'Medical'),
        ('miscellaneous', 'Miscellaneous'),
    ], string='Category', required=True, default='all',
        help='Expense category this policy applies to. "All" applies globally.')

    max_amount = fields.Float(
        string='Maximum Amount', digits=(16, 2), default=0,
        help='Maximum allowed expense amount in company currency. 0 = no limit.'
    )
    require_receipt = fields.Boolean(
        string='Require Receipt', default=False,
        help='If checked, a receipt must be attached for expenses in this category.'
    )
    receipt_threshold = fields.Float(
        string='Receipt Required Above', digits=(16, 2), default=0,
        help='Receipt is required only for expenses above this amount. 0 = always required.'
    )
    description = fields.Text(
        string='Policy Description',
        help='Detailed description of this policy for reference.'
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('max_amount_positive', 'CHECK(max_amount >= 0)',
         'Maximum amount must be zero or positive.'),
        ('receipt_threshold_positive', 'CHECK(receipt_threshold >= 0)',
         'Receipt threshold must be zero or positive.'),
    ]

    @api.constrains('category', 'company_id')
    def _check_unique_category(self):
        """Warn if duplicate active policies exist for same company + category."""
        for rec in self:
            duplicates = self.search([
                ('id', '!=', rec.id),
                ('company_id', '=', rec.company_id.id),
                ('category', '=', rec.category),
                ('active', '=', True),
            ])
            if duplicates and rec.active:
                raise ValidationError(_(
                    'An active policy already exists for category "%s" in company "%s". '
                    'Please deactivate the existing one first.'
                ) % (rec.category, rec.company_id.name))
