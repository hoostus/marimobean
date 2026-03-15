import marimo

__generated_with = "0.20.4"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(df, pn, today, ytd_spend):
    _doy = round(today.timetuple().tm_yday / 365 * 100)
    _spend = round((ytd_spend / df['Tilt PMT'] * 100).item())
    pn.panel(f"""# {today}
    Date: {_doy}%

    Tilt: {_spend}%
    """)
    return


@app.cell(hide_code=True)
def _(df, pl, pn, projected, ytd_spend):
    _ytd = pn.indicators.Number(
        name = 'YTD Spend',
        value = ytd_spend.item(),
        format = '${value:,.0f}',
        colors = [(0, 'red'), (500_000, 'green')]
    )

    _p = projected / 1000
    _p = _p.with_columns(pl.all().floor()) * 1000

    _projected = pn.indicators.Number(
        name = 'Projected Spend',
        value = _p.item(),
        format = '${value:,.0f}',
        colors = [(0, 'white'), (500_000, 'grey')]
    )

    _tiltpmt = pn.indicators.Number(
        name = 'Tilt PMT',
        value = df['Tilt PMT'].item(),
        format = '${value:,.0f}',
        colors = [(0, 'red'), (500_000, 'green')]
    )

    _rawpmt = pn.indicators.Number(
        name = 'Raw PMT',
        value = df['Raw PMT'].item(),
        format = '${value:,.0f}',
        colors = [(0, 'white'), (500_000, 'grey')]
    )

    pn.GridBox(_ytd, _projected, _tiltpmt, _rawpmt, ncols=2)
    return


@app.cell(hide_code=True)
def _(datetime, run_query, today):
    # Estimate our projected spending for the year based on past expenses
    # and what we've spent so far this year.
    _jan_1 = datetime.date(today.year, 1, 1)

    ytd_spend = run_query(f"""
    select
        sum(convert(cost(position), 'AUD', date)) as balance
    where
        account ~ 'Expenses:'
        and date >= {_jan_1}
    """)


    def estimate_spending():
        start_trend = datetime.date(2025, 1, 1)
        days_since = today - start_trend
        day_of_year = today.timetuple().tm_yday

        # We're trying to get estimate of "required" or
        # "non-discretionary" spending, which is always going
        # to be a somewhat fuzzy & arbitrary distinction. We will
        # remove accounts that are "discretionary" or "one-off"
        total_spend = run_query(f"""
        select
            sum(convert(cost(position), 'AUD', date)) as balance
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
    projected = estimate_spending()
    return projected, ytd_spend


@app.cell(hide_code=True)
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
    # Dividend Estimates
    """)
    return


@app.cell
def _(run_query):
    _balances = run_query(f"""
    select date, balance from #postings
    where account in
                (select account from #accounts where open.meta['include_in_dash'] = 'true')
    order by date
    """).fill_null(0)

    _dividends = run_query(f"""
    select account,date,abs(position) as amount
    from #postings
    where account ~ 'Income:Dividends'
    order by date
    """)

    dividends = _dividends.join_asof(_balances, on='date', strategy='backward')

    recent = dividends.sort('date').group_by('account').tail(8)

    veu = recent.filter(recent['account'] == 'Income:Dividends:VEU')
    veu_amt = float(veu['balance (VEU_AX)'].last())
    veu_amt * (veu['amount (AUD)'] / veu['balance (VEU_AX)']).mean()
    return


@app.cell(hide_code=True)
def _(datetime):
    today = datetime.date.today()
    return (today,)


@app.cell(hide_code=True)
def _(pl, pmt_raw_aud, pmt_tilt_aud):
    df = pl.DataFrame(data={'Tilt PMT': pmt_tilt_aud, 'Raw PMT': pmt_raw_aud})
    df = df.with_columns(pl.all()) / 1000
    df = df.with_columns(pl.all().floor()) * 1000
    return (df,)


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
