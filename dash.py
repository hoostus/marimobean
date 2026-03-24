import marimo

__generated_with = "0.21.1"
app = marimo.App(width="medium")


@app.cell
def _(datetime):
    today = datetime.date.today()
    return (today,)


@app.cell
def _(datetime, pl, today):
    # We build a dataframe for expected returns to allow us to vary it over time.

    def build_expected_returns_dataframe():
        start_date = datetime.date(today.year, 1, 1)
        end_date = datetime.date.today()
        df = pl.date_range(
            start=start_date, 
            end=end_date, 
            interval="1d", 
            eager=True
        ).alias("date").to_frame()
        df = df.with_columns(
            rate = pl.when(pl.col("date") < datetime.date(datetime.date.today().year, 2, 23))
            .then(pl.lit(0.032))
            .otherwise(pl.lit(0.031))
        )
        return df
    expected_returns = build_expected_returns_dataframe()
    return (expected_returns,)


@app.cell
def _(today):
    # Build our life expectancy. We don't need a dataframe because this isn't going to vary substantially over the
    # course of the few months we're looking at here.

    import life_expectancy as life

    age_1 = today.year - 1975
    age_2 = today.year - 1990

    life_expectancy = life.get_conservative_life_expectancy(
        life.male, age_1,
        life.female, age_2
    )
    return (life_expectancy,)


@app.cell
def _():
    # We also don't need a dataframe from the bequest: how much you want left in the portfolio at the end of the
    # period (when you are dead).
    bequest = 0
    return (bequest,)


@app.cell
def _(mo, pmt_df, today, ytd_spend):
    _doy = round(today.timetuple().tm_yday / 365 * 100)
    _spend = round((ytd_spend / pmt_df['Tilt PMT'] * 100).item())

    if _doy >= _spend:
        _style = 'green'
    else:
        _style = 'red'

    mo.hstack((mo.md(f'# {today}'),
                mo.md(f"Tilt: {_spend}%").style(color=_style),
                mo.md(f"Date: {_doy}%").style(color='grey')))
    return


@app.cell
def _(run_query, today):
    def get_nw(date):
        df = run_query(f"""
            select convert(sum(position), 'USD', {date}) as amount
            where account ~ 'Assets:'
        """)
        usd = df['amount (USD)'].item()
        return float(usd)

    get_nw(today.isoformat())
    return (get_nw,)


@app.cell
def _(bequest, expected_returns, get_nw, life_expectancy, pl, pmt, pv, today):
    def calculate_pmt(date):
        networth = get_nw(date)

        er = expected_returns.filter(pl.col('date') == today)['rate'].item()
        pmt_raw = -pmt(er, life_expectancy, networth, bequest, 1)

        target_portfolio = 750_000
        portfolio_tilt = 0.5
        pmt_portfolio_tilt = pmt_raw * pow(networth / target_portfolio, portfolio_tilt)

        target_income_aud = 225_000
        target_income_portfolio = pv(er, life_expectancy, -target_income_aud, 0)
        income_tilt = -0.5
        pmt_income_tilt = pmt_raw * pow(networth / target_income_portfolio, income_tilt)

        pmt_tilt = min(pmt_portfolio_tilt, pmt_income_tilt)

        _df = pl.DataFrame(data={'Tilt PMT': pmt_tilt, 'Raw PMT': pmt_raw})
        _df = _df.with_columns(pl.all()) / 1000
        pmt_df = _df.with_columns(pl.all().floor()) * 1000

        return pmt_df
    pmt_df = calculate_pmt(today.isoformat())
    pmt_df
    return (pmt_df,)


@app.cell
def _(pmt_df, pn, projected, ytd_spend):
    _ytd = pn.indicators.Number(
        name = 'YTD Spend',
        value = ytd_spend.item(),
        format = '${value:,.0f}',
        colors = [(0, 'red'), (500_000, 'green')]
    )

    _projected = pn.indicators.Number(
        name = 'Projected Spend',
        value = projected.item(),
        format = '${value:,.0f}',
        colors = [(0, 'white'), (500_000, 'grey')]
    )

    _tiltpmt = pn.indicators.Number(
        name = 'Tilt PMT',
        value = pmt_df['Tilt PMT'].item(),
        format = '${value:,.0f}',
        colors = [(0, 'red'), (500_000, 'green')]
    )

    _rawpmt = pn.indicators.Number(
        name = 'Raw PMT',
        value = pmt_df['Raw PMT'].item(),
        format = '${value:,.0f}',
        colors = [(0, 'white'), (500_000, 'grey')]
    )

    pn.GridBox(_ytd, _projected, _tiltpmt, _rawpmt, ncols=2)
    return


@app.cell
def _(datetime, run_query, today):
    # Estimate our projected spending for the year based on past expenses
    # and what we've spent so far this year.
    _jan_1 = datetime.date(2015, 1, 1)

    ytd_spend = run_query(f"""
    select
        sum(convert(cost(position), 'USD', date)) as balance
    where
        account ~ 'Expenses:'
        and date >= {_jan_1}
    """)['balance (USD)']

    def estimate_spending():
        start_trend = datetime.date(2015, 1, 1)
        days_since = today - start_trend
        day_of_year = today.timetuple().tm_yday

        # We're trying to get estimate of "required" or
        # "non-discretionary" spending, which is always going
        # to be a somewhat fuzzy & arbitrary distinction. We will
        # remove accounts that are "discretionary" or "one-off"
        total_spend = run_query(f"""
        select
            sum(convert(cost(position), 'USD', date)) as balance
        where
            account ~ 'Expenses:'
            and not account ~ 'Expenses:Vacation:'
            and account != 'Expenses:Everyday:Household-Goods'
            and account != 'Expenses:Everyday:House-Renovation'
            and date >= {start_trend.isoformat()}
        """)

        daily_spend = total_spend / days_since.days
        days_left = 365 - day_of_year
        remainder = daily_spend * days_left
        estimate = ytd_spend + remainder

        return estimate
    projected = estimate_spending()['balance (USD)']
    return projected, ytd_spend


@app.cell
def _(run_query):
    # This shows all holdings.

    run_query(f"""
    SELECT account,
        units(sum(position)) as units,
        cost_number as cost,
        first(getprice(currency, cost_currency)) as price,
        cost(sum(position)) as book_value,
        value(sum(position)) as market_value,
        cost_date as acquisition_date
      WHERE account_sortkey(account) ~ "^[01]"
      GROUP BY account, cost_date, currency, cost_currency, cost_number, account_sortkey(account)
      ORDER BY account_sortkey(account), currency, cost_date
    """)
    return


@app.cell
def _(run_query):
    _df = run_query(f"""
    SELECT
        units(sum(position)) as units
    WHERE
        account ~ 'Assets:'
    """)

    # the column names are 'units (GLD)' and we just want 'GLD'
    _df = _df.rename(lambda c: c.replace('units (', '')).rename(lambda c: c.replace(')', ''))
    _df
    return


@app.cell
def _(run_query):
    # Addition income that we are free to spend above and beyond what the portfolio
    # allows.
    income = run_query(f"""
    select
        abs(sum(convert(cost(position), 'AUD', date))) as Income
    where
        (account = 'Income:Salary' or account = 'Income:Rent' or account = 'Income:Interest:SecuritiesLending')
        and year = year(today())
    """)
    return


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


@app.function
def display(d):
    """ We get rid of needless precision, which makes it hardesr to parse things,
    and only display things to the nearest thousand. """
    return int(round(d, -3))


@app.cell
def _(entries, options, pl, run_bql_query):
    def run_query(query):
        """ Convert a beancount BQL query result to a polars dataframe """
        cols, rows = run_bql_query(entries, options, query, numberify=True)
        schema = [k.name for k in cols]
        df = pl.DataFrame(schema=schema, data=rows, orient='row', infer_schema_length=None)
        return df

    return (run_query,)


@app.cell
def _(beancount_file, load_file, printer):
    entries, _errors, options = load_file(beancount_file)
    printer.print_errors(_errors)
    return entries, options


@app.cell
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
    from beancount.core import data

    import datetime
    from pathlib import Path
    import math

    from numpy_financial import pmt, pv
    from decimal import Decimal

    home_dir = Path.home()
    return datetime, load_file, mo, pl, pmt, pn, printer, pv, run_bql_query


@app.cell
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
