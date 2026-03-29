# -*- coding: utf-8 -*-

from odoo import models, fields


class WorkflowStep(models.Model):
    _name = 'workflow.step'
    _description = 'Workflow Approval Step'
    _order = 'sequence, id'

    workflow_id = fields.Many2one(
        'approval.workflow', string='Workflow',
        required=True, ondelete='cascade'
    )
    sequence = fields.Integer(string='Step Order', default=10, required=True)
    name = fields.Char(string='Step Name', required=True,
        help='E.g., Manager Review, Finance Approval, Director Sign-off')

    approver_type = fields.Selection([
        ('manager', 'Employee\'s Manager'),
        ('specific_user', 'Specific User(s)'),
        ('role_based', 'Role-Based (Group)'),
    ], string='Approver Type', required=True, default='specific_user',
        help="""
        Manager: The expense submitter's direct manager.
        Specific User(s): One or more named approvers.
        Role-Based: Any user in the specified security group.
        """
    )
    approver_ids = fields.Many2many(
        'res.users', 'workflow_step_approver_rel',
        'step_id', 'user_id',
        string='Approvers',
        help='Specific users who can approve at this step (for Specific User type).',
        domain="[('expense_role', 'in', ['manager', 'admin'])]"
    )
    role_group_id = fields.Many2one(
        'res.groups', string='Approver Group',
        help='Security group whose members can approve at this step (for Role-Based type).'
    )
