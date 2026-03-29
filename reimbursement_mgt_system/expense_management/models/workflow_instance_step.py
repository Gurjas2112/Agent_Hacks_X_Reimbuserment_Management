# -*- coding: utf-8 -*-

from odoo import models, fields, api


class WorkflowInstanceStep(models.Model):
    _name = 'workflow.instance.step'
    _description = 'Workflow Instance Step (Runtime)'
    _order = 'sequence, id'

    instance_id = fields.Many2one(
        'workflow.instance', string='Workflow Instance',
        required=True, ondelete='cascade'
    )
    step_id = fields.Many2one(
        'workflow.step', string='Workflow Step',
        help='Reference to the original workflow step config (may be empty for auto-manager step).'
    )
    sequence = fields.Integer(string='Step Order', required=True)
    name = fields.Char(string='Step Name', required=True)

    approver_ids = fields.Many2many(
        'res.users', 'wf_instance_step_approver_rel',
        'instance_step_id', 'user_id',
        string='Assigned Approvers'
    )
    approved_by_ids = fields.Many2many(
        'res.users', 'wf_instance_step_approved_rel',
        'instance_step_id', 'user_id',
        string='Approved By'
    )
    rejected_by_id = fields.Many2one(
        'res.users', string='Rejected By'
    )

    status = fields.Selection([
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], string='Status', default='pending')

    approvals_required = fields.Integer(
        string='Approvals Required', compute='_compute_approvals'
    )
    approvals_done = fields.Integer(
        string='Approvals Done', compute='_compute_approvals'
    )

    @api.depends('approver_ids', 'approved_by_ids')
    def _compute_approvals(self):
        for step in self:
            step.approvals_required = len(step.approver_ids)
            step.approvals_done = len(step.approved_by_ids)
