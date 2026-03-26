import marimo

__generated_with = "0.21.1"
app = marimo.App(width="medium")


@app.cell
def _(entries):
    from beancount.core import inventory, convert
    from beancount.core.data import Transaction, Commodity, Open, Balance, Price, Event

    import collections

    commodities = set()
    ignored_currencies = set(['USD', 'IRAUSD', 'VACHR'])
    inv = inventory.Inventory()
    inv_dates = {}

    # this doesn't work....there could be multiple things on a single day
    # need to coalesce across everything on a given day. ugh.

    for entry in entries:
        if isinstance(entry, Transaction):
            date = entry.date
            for p in entry.postings:
                if p.units.currency not in ignored_currencies:
                    inv.add_amount(p.units)
                    if not inv.is_empty():
                        p = {}
                        for position in inv.get_positions():
                            p[position.units.currency] = position.units.number
                        inv_dates[date] = p
        elif isinstance(entry, Commodity):
            # there shouldn't be any duplicates here but use a set
            # just in case
            commodities.add(entry.currency)
        elif isinstance(entry, Open): pass
        elif isinstance(entry, Price): pass
        elif isinstance(entry, Balance): pass
        elif isinstance(entry, Event): pass
        else:
            print('Unknown type: ', entry)

    inv_dates
    return


@app.cell
def _(run_query):
    prices = run_query(f"""
        select * from #prices
    """)

    # we need to sorta unpivot for currency/amount for the anti-join

    prices.partition_by('currency')
    return (prices,)


@app.cell
def _(pl, prices):
    first_date = prices['date'].first()
    last_date = prices['date'].last()

    full_range = pl.date_range(
        start = first_date,
        end = last_date,
        interval = '1d',
        eager = True
    ).alias('date').to_frame()
    return (full_range,)


@app.cell
def _(full_range, pl, prices):
    missing = []

    for df in prices.partition_by('currency'):
        currency = df['currency'].first()

        # we don't actually want the full range,
        # we really only care about when we first acquired something
        # not sure how to get that yet. And we also don't care
        # after it went to zero in our holdings.
        # So we really a series/df of dates when we held each thing.
        m = full_range.join(df, on='date', how='anti')
        missing.append(m.with_columns(currency = pl.lit(currency)))

    pl.concat(missing).sort(pl.col('date'))
    return


@app.cell(hide_code=True)
def _(entries, options, pl, run_bql_query):
    def run_query(query):
        """ Convert a beancount BQL query result to a polars dataframe """
        cols, rows = run_bql_query(entries, options, query, numberify=True)
        schema = [k.name for k in cols]
        df = pl.DataFrame(schema=schema, data=rows, orient='row', infer_schema_length=None)
        return df

    return (run_query,)


@app.cell(hide_code=True)
def _(beancount_file, load_file, printer):
    entries, _errors, options = load_file(beancount_file)
    printer.print_errors(_errors)
    return entries, options


@app.cell(hide_code=True)
def _():
    import marimo as mo

    # Use altair for plotting data.
    import altair as alt

    # Use polars for dataframe manipulation.
    import polars as pl

    # Marimo uses great_tables internally but
    # we can also create our own for display
    # of dataframes
    from great_tables import GT

    # Panel provides another level of widgets
    # above and beyond great_tables.
    import panel as pn
    pn.extension()

    from beancount.loader import load_file
    from beancount.parser import printer
    from beanquery.query import run_query as run_bql_query

    import datetime
    from pathlib import Path

    home_dir = Path.home()
    return load_file, mo, pl, printer, run_bql_query


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""/// Attention | Edit this to point to your beancount file if you want to try on real data.""") if mo.app_meta().mode == 'edit' else None
    return


@app.cell
def _():
    #beancount_file = f'{home_dir}/Documents/beancount/my.bean'
    beancount_file = 'huge-example.beancount'
    return (beancount_file,)


if __name__ == "__main__":
    app.run()
