# -*- coding: utf-8 -*-
"""
Currency Service
================
Handles:
1. Country → Currency lookup from static country_currency.json
2. Real-time currency conversion via ExchangeRate API v6
"""

import json
import logging
import os

import requests

_logger = logging.getLogger(__name__)

# ExchangeRate API v6 configuration
EXCHANGE_RATE_API_KEY = "d626e2dd0a780145256e5f85"
EXCHANGE_RATE_URL = "https://v6.exchangerate-api.com/v6/{api_key}/latest/{base}"

# Cache for exchange rates (per-session, reduces API calls)
_rate_cache = {}


def get_country_currency(country_name):
    """
    Look up the primary currency code for a given country.

    Uses the static country_currency.json file (pre-loaded from restcountries.com).

    Args:
        country_name: Country name (e.g., 'India', 'United States')

    Returns:
        str: Currency code (e.g., 'INR', 'USD') or None if not found.
    """
    if not country_name:
        return None

    try:
        # Resolve path to country_currency.json
        module_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        json_path = os.path.join(module_path, 'data', 'country_currency.json')

        if not os.path.exists(json_path):
            _logger.error("country_currency.json not found at %s", json_path)
            return None

        with open(json_path, 'r', encoding='utf-8') as f:
            countries = json.load(f)

        country_lower = country_name.strip().lower()

        for entry in countries:
            name_data = entry.get('name', {})
            common = name_data.get('common', '').lower()
            official = name_data.get('official', '').lower()

            if country_lower in (common, official):
                currencies = entry.get('currencies', {})
                if currencies:
                    code = list(currencies.keys())[0]
                    _logger.info("Country '%s' → Currency '%s'", country_name, code)
                    return code

        _logger.warning("Country '%s' not found in currency data", country_name)
        return None

    except Exception as e:
        _logger.error("Error looking up country currency: %s", str(e))
        return None


def get_exchange_rate(from_currency, to_currency):
    """
    Get the exchange rate between two currencies.

    Uses ExchangeRate API v6 with the configured API key.

    Args:
        from_currency: Source currency code (e.g., 'USD')
        to_currency: Target currency code (e.g., 'INR')

    Returns:
        float: Exchange rate (e.g., 83.12 means 1 USD = 83.12 INR)

    Raises:
        Exception: If the API call fails or currencies are invalid.
    """
    from_currency = from_currency.upper().strip()
    to_currency = to_currency.upper().strip()

    if from_currency == to_currency:
        return 1.0

    # Check cache
    cache_key = f"{from_currency}_{to_currency}"
    if cache_key in _rate_cache:
        _logger.info("Using cached rate for %s → %s", from_currency, to_currency)
        return _rate_cache[cache_key]

    try:
        url = EXCHANGE_RATE_URL.format(
            api_key=EXCHANGE_RATE_API_KEY,
            base=from_currency
        )

        _logger.info("Fetching exchange rate: %s → %s", from_currency, to_currency)
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        data = response.json()

        if data.get('result') == 'error':
            error_type = data.get('error-type', 'unknown')
            raise Exception(f"ExchangeRate API error: {error_type}")

        rates = data.get('conversion_rates', {})
        rate = rates.get(to_currency)

        if rate is None:
            raise Exception(
                f"Currency '{to_currency}' not found in conversion rates. "
                f"Available: {list(rates.keys())[:10]}..."
            )

        # Cache the rate
        _rate_cache[cache_key] = rate
        _logger.info("Exchange rate: 1 %s = %s %s", from_currency, rate, to_currency)

        return rate

    except requests.exceptions.Timeout:
        raise Exception("Exchange rate API request timed out. Please try again.")
    except requests.exceptions.ConnectionError:
        raise Exception("Could not connect to exchange rate API. Check internet connection.")
    except requests.exceptions.HTTPError as e:
        raise Exception(f"Exchange rate API HTTP error: {e}")
    except Exception as e:
        _logger.error("Exchange rate lookup failed: %s", str(e))
        raise


def convert_currency(amount, from_currency, to_currency):
    """
    Convert an amount from one currency to another.

    Args:
        amount: Amount to convert (float)
        from_currency: Source currency code
        to_currency: Target currency code

    Returns:
        float: Converted amount
    """
    if from_currency == to_currency:
        return amount

    rate = get_exchange_rate(from_currency, to_currency)
    converted = amount * rate

    _logger.info(
        "Converted %.2f %s → %.2f %s (rate: %s)",
        amount, from_currency, converted, to_currency, rate
    )

    return round(converted, 2)


def clear_rate_cache():
    """Clear the cached exchange rates."""
    global _rate_cache
    _rate_cache = {}
    _logger.info("Exchange rate cache cleared")
