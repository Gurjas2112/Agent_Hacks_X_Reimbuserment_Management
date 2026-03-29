# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ApprovalWorkflow(models.Model):
    _name = 'approval.workflow'
    _description = 'Approval Workflow Configuration'
    _order = 'name'

    name = fields.Char(string='Workflow Name', required=True)
    company_id = fields.Many2one(
        'expense.company', string='Company', required=True,
        help='Company this workflow belongs to.'
    )
    rule_type = fields.Selection([
        ('sequential', 'Sequential (Step-by-Step)'),
        ('percentage', 'Percentage Threshold'),
        ('specific_approver', 'Specific Approver Override'),
        ('hybrid', 'Hybrid (Percentage + Specific Approver)'),
    ], string='Rule Type', required=True, default='sequential',
        help="""
        Sequential: Each step must be approved in order.
        Percentage: Expense approved when threshold % of approvers approve.
        Specific Approver: Auto-approved if a specific person (e.g., CFO) approves.
        Hybrid: Approved if EITHER percentage threshold OR specific approver approves.
        """
    )
    percentage_threshold = fields.Float(
        string='Approval Percentage (%)', default=60.0,
        help='Minimum percentage of approvals required (for percentage/hybrid rules).'
    )
    specific_approver_id = fields.Many2one(
        'res.users', string='Specific Approver',
        help='If this person approves at any step, the expense is auto-approved (for specific_approver/hybrid rules).',
        domain="[('expense_role', 'in', ['manager', 'admin'])]"
    )
    is_manager_first = fields.Boolean(
        string='Manager Approves First', default=True,
        help='If checked, the employee\'s direct manager is automatically added as Step 1.'
    )
    step_ids = fields.One2many(
        'workflow.step', 'workflow_id', string='Approval Steps',
        copy=True
    )
    active = fields.Boolean(default=True)
    description = fields.Text(string='Description',
        help='Describe the purpose and rules of this workflow.')

    step_count = fields.Integer(
        string='Steps', compute='_compute_step_count'
    )

    @api.depends('step_ids')
    def _compute_step_count(self):
        for rec in self:
            rec.step_count = len(rec.step_ids)
