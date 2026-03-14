import marimo

__generated_with = "0.20.4"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(df, pn):
    _a = pn.indicators.Number(
        name = 'Tilt PMT',
        value = df['Tilt PMT'].item(),
        format = '${value:,.0f}',
        colors = [(0, 'red'), (500_000, 'green')]
    )

    _b = pn.indicators.Number(
        name = 'Raw PMT',
        value = df['Raw PMT'].item(),
        format = '${value:,.0f}',
        colors = [(0, 'white'), (500_000, 'grey')]
    )
    pn.Row(_a, _b)
    return


@app.cell
def _(run_query):
    balances = run_query(f"""
    select date, amount from #balances
    where account in
                (select account from #accounts where open.meta['include_in_dash'] = 'true')
    and currency(amount) != 'AUD' and currency(amount) != 'USD'
    order by date
    """)

    dividends = run_query(f"""
    select account,date,weight
    from #postings
    where account ~ 'Income:Dividends'
    order by date
    """)

    dividends.join_asof(balances, on='date', strategy='backward')
    return


@app.cell(hide_code=True)
def _(pl, pmt_raw_aud, pmt_tilt_aud):
    df = pl.DataFrame(data={'Tilt PMT': pmt_tilt_aud, 'Raw PMT': pmt_raw_aud})
    df = df.with_columns(pl.all()) / 1000
    df = df.with_columns(pl.all().floor()) * 1000
    return (df,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""/// Attention | Edit this to point to your beancount file if you want to try on real data.""") if mo.app_meta().mode == 'edit' else None
    return


@app.cell
def _(home_dir):
    beancount_file = f'{home_dir}/Documents/beancount/my.bean'
    #beancount_file = 'huge-example.beancount'
    return (beancount_file,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    /// admonition | We only consider accounts with the metadata *include_in_dash* set to *true*

    ```
    2025-01-01 open Assets:Investing
      include_in_dash: "true"
    ```
    """)  if mo.app_meta().mode == 'edit' else None
    return


@app.cell(hide_code=True)
def _(get_price, run_query):
    def get_nw():
        df = run_query(f"""
            select convert(sum(position), 'USD', today()) as amount
            where account in
                (select account from #accounts where open.meta['include_in_dash'] = 'true')
        """)
        usd = df['amount (USD)'].item()
        # beancount can't convert FSS_INTL to USD (only to AUD) because it doesn't do transitive conversions...
        fss = df['amount (FSS_INTL)'].item()
        fss_aud = fss * get_price('FSS_INTL')['amount (AUD)'].item()
        fss_usd = fss_aud * get_price('AUD')['amount (USD)'].item()
        return usd + fss_usd
    networth = get_nw()
    return (networth,)


@app.cell(hide_code=True)
def _(datetime, mo, run_query):
    _df = run_query(f"""
        select * from #prices;
    """)

    most_recent_price = _df.sort('date').group_by('currency').last()
    def get_price(commodity):
        return most_recent_price.filter(most_recent_price['currency'] == commodity)

    _aud_df = get_price('AUD')
    aud_usd = _aud_df['amount (USD)'].item()

    mo.md(f""" /// Attention | USD:AUD exchange rate is stale.
    The most recent data is from {_df['date'].item()}.
    """) if datetime.date.today() - _aud_df['date'].item() > datetime.timedelta(days=5) else None
    return aud_usd, get_price


@app.function(hide_code=True)
def display(d):
    """ We get rid of needless precision, which makes it hardesr to parse things,
    and only display things to the nearest thousand. """
    return int(round(d, -3))


@app.cell(hide_code=True)
def _(Decimal, aud_usd, networth, pmt, pv):
    # How to make these more visible and if-possible self-updating?
    expected_returns = Decimal('0.031')
    life_expectancy = Decimal('72.335')
    bequest = Decimal(0)
    pmt_raw = -pmt(expected_returns, life_expectancy, networth, bequest, 1)
    pmt_raw_aud = pmt_raw / aud_usd

    target_portfolio = Decimal(5_000_000)
    portfolio_tilt = Decimal('0.5')
    pmt_portfolio_tilt = pmt_raw * pow(networth / target_portfolio, portfolio_tilt)

    target_income_aud = 225_000
    target_income_usd = target_income_aud * aud_usd
    target_income_portfolio = pv(expected_returns, life_expectancy, -target_income_usd, 0)
    income_tilt = Decimal('-0.5')
    pmt_income_tilt = pmt_raw * pow(networth / target_income_portfolio, income_tilt)

    pmt_tilt = min(pmt_portfolio_tilt, pmt_income_tilt)

    pmt_tilt_aud = pmt_tilt / aud_usd
    return pmt_raw_aud, pmt_tilt_aud


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
    import altair as alt
    import polars as pl
    from great_tables import GT
    import panel as pn
    pn.extension()

    from beancount.loader import load_file
    from beancount.parser import printer
    from beanquery.query import run_query as run_bql_query

    import datetime
    from pathlib import Path

    from numpy_financial import pmt, pv
    from decimal import Decimal

    home_dir = Path.home()
    return (
        Decimal,
        datetime,
        home_dir,
        load_file,
        mo,
        pl,
        pmt,
        pn,
        printer,
        pv,
        run_bql_query,
    )


if __name__ == "__main__":
    app.run()
