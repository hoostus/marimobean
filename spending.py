import marimo

__generated_with = "0.20.4"
app = marimo.App(width="medium")


@app.cell
def _(alt, end_date, mo, networth, start_date):
    mo.ui.altair_chart(alt.Chart(networth).mark_line(point=True)
        .encode(x=alt.X('date', title='Date'),
                y=alt.Y('net_worth', title='Net Worth', axis=alt.Axis(format='$,.0f')),
                tooltip=[alt.Tooltip('date', title='Date'), alt.Tooltip('net_worth', title='Net worth', format='$,.0f')])
        .properties(title=alt.Title('Net Worth', subtitle=f"{start_date} to {end_date}")))
    return


@app.cell
def _():
    account_re = 'Assets:US:Schwab:Brokerage|Assets:US:Vanguard|Assets:US:Interactive-Brokers|Assets:AUS:First-State-Super'

    CURRENCY = 'AUD'
    return CURRENCY, account_re


@app.cell
def _(datetime):
    start_date = datetime.date(datetime.date.today().year, 1, 1)
    end_date = datetime.date.today()
    return end_date, start_date


@app.cell
def _(
    CURRENCY,
    account_re,
    beancount,
    datetime,
    end_date,
    entries,
    options,
    start_date,
    summator,
):
    def daterange(start_date: datetime.date, end_date: datetime.date):
        days = int((end_date - start_date).days)
        for n in range(days):
            yield start_date + datetime.timedelta(n)

    def get_nws(start_date, end_date, account_re):
        summer = summator.BeanSummator(entries, options, account_re)

        price_map = beancount.core.prices.build_price_map(entries)

        nws = {'date': [], 'net_worth': []}

        for d in daterange(start_date, end_date):
            sum = summer.sum_till_date(d)
            nws['date'].append(d.isoformat())
            nws['net_worth'].append(sum.convert(CURRENCY, price_map, d).sum_all().get_currency_units(CURRENCY).number)

        return nws
    nws = get_nws(start_date, end_date, account_re)
    return (nws,)


@app.cell
def _(nws, pl):
    networth = pl.DataFrame(nws, schema={'date': pl.Date, 'net_worth': pl.Decimal(scale=2)})
    networth
    return (networth,)


@app.cell
def _(datetime, pl):
    def get_days_in_year():
        current_year = datetime.date.today().year
        days_in_year = (
            (pl.date(current_year + 1, 1, 1) - pl.date(current_year, 1, 1))
            .dt.total_days())
        return days_in_year

    return (get_days_in_year,)


@app.cell
def _(get_days_in_year, networth, pl):
    from numpy_financial import pmt, pv

    _nw = networth
    _nw = _nw.with_columns(rate = pl.lit(0.031))
    _nw = _nw.with_columns(nper = pl.lit(72.335))
    _nw = _nw.with_columns(fv = pl.lit(0))
    _nw = _nw.with_columns(pl.col('net_worth').cast(float))
    pmts = -pmt(_nw['rate'], _nw['nper'], _nw['net_worth'], _nw['fv'])
    _nw = _nw.with_columns(pl.Series('pmt', pmts, dtype=pl.Decimal(scale=2)))
    _nw = _nw.with_columns(day_of_year = pl.col('date').dt.ordinal_day())

    tilt_pmt = _nw.clone()

    _nw = _nw.with_columns(daily_spend = pl.col('pmt') / get_days_in_year())
    _nw = _nw.with_columns(target = pl.col('daily_spend') * pl.col('day_of_year'))

    raw_pmt = _nw
    _nw
    return (tilt_pmt,)


@app.cell
def _(pl, tilt_pmt):
    target_portfolio = 7_000_000
    tilt = 0.5

    _pmt = tilt_pmt.with_columns(target_frac = pl.col('net_worth') / target_portfolio)
    _pmt = _pmt.with_columns(tilt_factor = pl.col('target_frac').pow(tilt))
    _pmt = _pmt.with_columns(tilt_pmt = pl.col('pmt') * pl.col('tilt_factor'))
    _pmt = _pmt.with_columns(pl.col('tilt_pmt').cast(pl.Decimal(scale=2)))
    _pmt
    return


@app.cell(hide_code=True)
def _(entries, options, pl, run_bql_query):
    def run_query(query):
        """ Convert a beancount BQL query result to a polars dataframe """
        cols, rows = run_bql_query(entries, options, query, numberify=True)
        schema = [k.name for k in cols]
        df = pl.DataFrame(schema=schema, data=rows, orient='row', infer_schema_length=None)
        return df

    return


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
    import beancount.core.prices

    import datetime
    from pathlib import Path

    import summator

    home_dir = Path.home()
    return (
        alt,
        beancount,
        datetime,
        home_dir,
        load_file,
        mo,
        pl,
        printer,
        run_bql_query,
        summator,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""/// Attention | Edit this to point to your beancount file if you want to try on real data.""") if mo.app_meta().mode == 'edit' else None
    return


@app.cell
def _(home_dir):
    beancount_file = f'{home_dir}/Documents/beancount/my.bean'
    #beancount_file = 'huge-example.beancount'
    return (beancount_file,)


if __name__ == "__main__":
    app.run()
