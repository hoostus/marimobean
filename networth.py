import marimo

__generated_with = "0.20.4"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Even Faster Net Worth Chart

    Uses fastnetworth to calculate networth even faster.
    """)
    return


@app.cell
def _(mo, year_slider):
    _start_year = year_slider.value[0]
    _end_year = year_slider.value[1]
    mo.vstack([mo.md(f"Years selected to query: {_start_year} - {_end_year}"), year_slider])
    return


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
    #_account_re = 'Assets:US:Schwab:Brokerage|Assets:US:Vanguard|Assets:US:Interactive-Brokers|Assets:AUS:First-State-Super'
    account_re = 'Assets|Liabilities'

    #CURRENCY = 'AUD'
    CURRENCY = 'USD'
    return CURRENCY, account_re


@app.cell
def _(mo, run_query):
    _df = run_query("""select year, month order by date""")
    year_slider = mo.ui.range_slider(
        start = _df[0]['year'].item(),
        stop = _df[-1]['year'].item(),
        full_width=True
    )
    return (year_slider,)


@app.cell
def _(datetime, year_slider):
    #start_date = datetime.date(today.year, 1, 1)
    start_date = datetime.date(year_slider.value[0], 1, 1)

    #end_date = datetime.date.today()
    end_date = datetime.date(year_slider.value[1], 12, 31)
    return end_date, start_date


@app.cell
def _(
    CURRENCY,
    account_re,
    datetime,
    end_date,
    entries,
    get_networth_series,
    start_date,
    time,
):
    def daterange(start_date: datetime.date, end_date: datetime.date):
        days = int((end_date - start_date).days)
        for n in range(days):
            yield start_date + datetime.timedelta(n)

    _t0 = time.perf_counter()
    nws = get_networth_series(entries, CURRENCY, daterange(start_date, end_date), account_re)
    #print(f"get_networth_series took {time.perf_counter() - _t0:.3f}s")
    return (nws,)


@app.cell
def _(nws, pl):
    networth = pl.DataFrame(nws, schema={'date': pl.Date, 'net_worth': pl.Decimal(scale=2)})
    networth
    return (networth,)


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
    import time
    from pathlib import Path

    from fastnetworth import get_networth_series

    home_dir = Path.home()
    return (
        alt,
        datetime,
        get_networth_series,
        load_file,
        mo,
        pl,
        printer,
        run_bql_query,
        time,
    )


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
