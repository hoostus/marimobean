from beancount.core import data
from collections import defaultdict
from decimal import Decimal
import re

DEFAULT_ACCOUNT_CATEGORIES = [
    ('Cash and Bank Accounts', re.compile(r'^Assets:.*:(Banks|Cash):')),
    ('Investments', re.compile(r'^Assets:.*:Investments:')),
    ('Other Assets', re.compile(r'^Assets:')),
    ('Liabilities/Credit Cards', re.compile(r'^Liabilities:.*:CreditCards:')),
    ('Other Liabilities', re.compile(r'^Liabilities:')),
]


def make_classifier(categories=None):
    """Return a (classify_function, category_order_dict) from a categories list.

    categories is a list of (name, compiled_regex) tuples, checked in order.
    First match wins. Defaults to DEFAULT_ACCOUNT_CATEGORIES.
    """
    if categories is None:
        categories = DEFAULT_ACCOUNT_CATEGORIES
    order = {cat: i for i, (cat, _) in enumerate(categories)}

    def classify(account):
        for category, pattern in categories:
            if pattern.search(account):
                return category
        return 'Other'

    return classify, order



def get_networth_series(entries, target_currency, dates, account_re='Assets|Liabilities',
                        detail=False, classify_account=None):
    """O(N) computation of total net worth at each date across all accounts.

    N is the number of entries.  There are effectively 2 passes.
    dates must be an iterable of datetime.date in ascending order.
    account_re: regex to match account names (default: 'Assets|Liabilities').
    detail: if True, include per-account breakdown in the result.
    classify_account: optional function(account_name) -> category_string.
        Defaults to make_classifier() using DEFAULT_ACCOUNT_CATEGORIES.
    Returns: {'date': [...], 'net_worth': [...], 'detail': [...] (if detail=True)}
    """
    if classify_account is None:
        classify_account, _ = make_classifier()
    account_pattern = re.compile(account_re)
    running = defaultdict(list)
    cumulative = defaultdict(Decimal)
    prices = defaultdict(list)

    if detail:
        acct_running = defaultdict(list)
        acct_cumulative = defaultdict(Decimal)

    # Pass 1 - build running balances per currency and price database
    for entry in entries:
        if isinstance(entry, data.Transaction):
            for posting in entry.postings:
                if not account_pattern.search(posting.account):
                    continue
                currency = posting.units[1]
                amount = Decimal(posting.units[0])
                cumulative[currency] += amount
                running[currency].append((entry.date, cumulative[currency]))

                if detail:
                    key = (posting.account, currency)
                    acct_cumulative[key] += amount
                    acct_running[key].append((entry.date, acct_cumulative[key]))

        elif isinstance(entry, data.Price):
            if entry.currency != target_currency and entry.amount.currency == target_currency:
                prices[entry.currency].append((entry.date, Decimal(entry.amount.number)))

    # No sort needed — beancount loader guarantees entries are sorted by
    # (date, type_order, lineno), so running/prices lists are already in order.

    currencies = sorted(running.keys())
    state = {}
    for currency in currencies:
        state[currency] = {
            'ui': 0,
            'pi': 0,
            'cur_units': Decimal(0),
            'cur_price': Decimal(1) if currency == target_currency else None,
        }

    if detail:
        acct_keys = sorted(acct_running.keys())
        acct_state = {}
        for key in acct_keys:
            acct_state[key] = {'ui': 0, 'cur_units': Decimal(0)}

    # Pass 2 - compute net worth at each date
    nws = {'date': [], 'net_worth': []}
    if detail:
        nws['detail'] = []

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

        if detail:
            breakdown = {}
            for acct, currency in acct_keys:
                s = acct_state[(acct, currency)]
                units_list = acct_running[(acct, currency)]

                while s['ui'] < len(units_list) and units_list[s['ui']][0] <= d:
                    s['cur_units'] = units_list[s['ui']][1]
                    s['ui'] += 1

                if s['cur_units'] != 0:
                    price = state[currency].get('cur_price')
                    if price is not None:
                        value = s['cur_units'] * price
                        breakdown[(acct, currency)] = {
                            'units': s['cur_units'],
                            'price': price,
                            'value': value,
                            'category': classify_account(acct),
                        }
            nws['detail'].append(breakdown)

    return nws
