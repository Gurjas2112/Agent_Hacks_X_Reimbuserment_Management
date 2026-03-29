# -*- coding: utf-8 -*-

import json
import os
import logging

from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class ExpenseCompany(models.Model):
    _name = 'expense.company'
    _description = 'Expense Management Company'
    _inherit = ['mail.thread']

    name = fields.Char(string='Company Name', required=True, tracking=True)
    country = fields.Char(string='Country', required=True, tracking=True)
    currency_code = fields.Char(string='Currency Code', required=True, tracking=True,
                                help='Auto-set from country selection. This is the default currency for all expenses.')
    currency_symbol = fields.Char(string='Currency Symbol')
    admin_user_id = fields.Many2one('res.users', string='Admin User', readonly=True)
    employee_ids = fields.One2many('res.users', 'expense_company_id', string='Employees')
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Company name must be unique!'),
    ]

    @api.onchange('country')
    def _onchange_country(self):
        """Auto-set currency when country is selected by reading country_currency.json."""
        if not self.country:
            return

        try:
            # Load country_currency.json from module's data directory
            module_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            json_path = os.path.join(module_path, 'data', 'country_currency.json')

            if not os.path.exists(json_path):
                _logger.warning("country_currency.json not found at %s", json_path)
                return

            with open(json_path, 'r', encoding='utf-8') as f:
                countries = json.load(f)

            # Search for matching country (case-insensitive on common name)
            country_lower = self.country.strip().lower()
            for entry in countries:
                common_name = entry.get('name', {}).get('common', '').lower()
                official_name = entry.get('name', {}).get('official', '').lower()

                if country_lower in (common_name, official_name):
                    currencies = entry.get('currencies', {})
                    if currencies:
                        # Take the first currency
                        code = list(currencies.keys())[0]
                        self.currency_code = code
                        self.currency_symbol = currencies[code].get('symbol', '')
                        _logger.info("Set currency %s for country %s", code, self.country)
                    return

            _logger.warning("Country '%s' not found in country_currency.json", self.country)

        except Exception as e:
            _logger.error("Error reading country currency data: %s", str(e))

    @api.model
    def get_country_list(self):
        """Return list of available countries for selection."""
        try:
            module_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            json_path = os.path.join(module_path, 'data', 'country_currency.json')

            with open(json_path, 'r', encoding='utf-8') as f:
                countries = json.load(f)

            return sorted([
                entry.get('name', {}).get('common', '')
                for entry in countries
                if entry.get('name', {}).get('common', '')
            ])
        except Exception as e:
            _logger.error("Error loading country list: %s", str(e))
            return []
