#!/bin/bash
# =============================================================================
# Entrypoint wrapper for Odoo 19 + Expense Management
# =============================================================================
# Delegates to the official Odoo entrypoint after any first-run setup.
# =============================================================================

set -e

echo "=============================================="
echo "  Expense Management System — Odoo 19"
echo "=============================================="
echo "  Module path : /mnt/extra-addons/expense_management"
echo "  Odoo URL    : http://localhost:8069"
echo "  Master pwd  : admin_expense_2026"
echo "=============================================="

# Delegate to official Odoo entrypoint
exec /entrypoint.sh "$@"
