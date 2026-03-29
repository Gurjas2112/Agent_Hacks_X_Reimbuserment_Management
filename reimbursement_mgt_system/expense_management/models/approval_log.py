# -*- coding: utf-8 -*-

from odoo import models, fields


class ApprovalLog(models.Model):
    _name = 'approval.log'
    _description = 'Approval Audit Log'
    _order = 'timestamp desc'

    expense_id = fields.Many2one(
        'expense.claim', string='Expense Claim',
        required=True, ondelete='cascade', index=True
    )
    user_id = fields.Many2one(
        'res.users', string='User',
        required=True, index=True
    )
    action = fields.Selection([
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('escalated', 'Escalated'),
    ], string='Action', required=True)
    comment = fields.Text(string='Comment')
    timestamp = fields.Datetime(
        string='Timestamp', default=fields.Datetime.now,
        required=True, index=True
    )
    step_sequence = fields.Integer(string='Step Number', default=0)

    # Related for reporting
    employee_name = fields.Char(
        related='expense_id.employee_id.name',
        string='Employee', store=True
    )
    expense_amount = fields.Float(
        related='expense_id.amount_original',
        string='Expense Amount', store=True
    )
