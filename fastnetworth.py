from beancount.core import data
from collections import defaultdict
from decimal import Decimal
import re


def get_networth_series(entries, target_currency, dates, account_re='Assets|Liabilities'):
    """O(N) computation of total net worth at each date across all accounts.

    N is the number of entries.  There are effectively 2 passes.
    dates must be an iterable of datetime.date in ascending order.
    account_re: regex to match account names (default: 'Assets|Liabilities').
    Returns: {'date': [iso_date_str, ...], 'net_worth': [Decimal, ...]}
    
    NOTE: O(N) doesn't include the time to sort-by-date the running balances and prices
          (which may not be needed if Beancount already provides entries sorted by date)
          nor the Python data structure access times (e.g. dictionaries are maps)
    """
    account_pattern = re.compile(account_re)
    running = defaultdict(list)
    cumulative = defaultdict(Decimal)
    prices = defaultdict(list)

    # Pass 1 - build running balances per currency and price database
    for entry in entries:
        if isinstance(entry, data.Transaction):
            for posting in entry.postings:
                if not account_pattern.search(posting.account):
                    continue
                currency = posting.units[1]
                cumulative[currency] += Decimal(posting.units[0])
                running[currency].append((entry.date, cumulative[currency]))

        elif isinstance(entry, data.Price):
            if entry.currency != target_currency and entry.amount.currency == target_currency:
                prices[entry.currency].append((entry.date, Decimal(entry.amount.number)))

    # TODO: Not sure if this is needed.  Beancount may already provide entries sorted by date.
    for currency in running:
        running[currency].sort()
    for currency in prices:
        prices[currency].sort()

    currencies = sorted(running.keys())
    state = {}
    for currency in currencies:
        state[currency] = {
            'ui': 0,
            'pi': 0,
            'cur_units': Decimal(0),
            'cur_price': Decimal(1) if currency == target_currency else None,
        }

    # Pass 2 - compute net worth at each date, keeping track of the current units and price for each currency
    nws = {'date': [], 'net_worth': []}
    for d in dates:
        net_worth = Decimal(0)
        for currency in currencies:
            s = state[currency]
            units_list = running[currency]
            price_list = prices.get(currency, [])

            while s['ui'] < len(units_list) and units_list[s['ui']][0] <= d:
                s['cur_units'] = units_list[s['ui']][1]
                s['ui'] += 1
            while s['pi'] < len(price_list) and price_list[s['pi']][0] <= d:
                s['cur_price'] = price_list[s['pi']][1]
                s['pi'] += 1

            if s['cur_units'] != 0 and s['cur_price'] is not None:
                net_worth += s['cur_units'] * s['cur_price']

        nws['date'].append(d.isoformat())
        nws['net_worth'].append(net_worth)

    return nws
