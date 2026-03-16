import marimo

__generated_with = "0.20.4"
app = marimo.App(width="medium")


@app.cell
def _(datetime):
    today = datetime.date.today()
    return (today,)


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
def _(get_price, run_query):
    def get_nw(date):
        df = run_query(f"""
            select convert(sum(position), 'USD', {date}) as amount
            where account in
                (select account from #accounts where open.meta['include_in_dash'] = 'true')
        """)
        usd = df['amount (USD)'].item()
        # beancount can't convert FSS_INTL to USD (only to AUD) because it doesn't do transitive conversions...
        fss = df['amount (FSS_INTL)'].item()
        fss_aud = fss * get_price('FSS_INTL')['amount (AUD)'].item()
        fss_usd = fss_aud * get_price('AUD')['amount (USD)'].item()
        return usd + fss_usd

    return (get_nw,)


@app.cell
def _(Decimal, aud_usd, get_nw, pl, pmt, pv, today):
    def calculate_pmt(date):
    # How to make these more visible and if-possible self-updating?
        networth = get_nw(date)

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

        _df = pl.DataFrame(data={'Tilt PMT': pmt_tilt_aud, 'Raw PMT': pmt_raw_aud})
        _df = _df.with_columns(pl.all()) / 1000
        pmt_df = _df.with_columns(pl.all().floor()) * 1000

        return pmt_df
    pmt_df = calculate_pmt(today.isoformat())
    return (pmt_df,)


@app.cell
def _(pl, pmt_df, pn, projected, ytd_spend):
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


@app.cell(disabled=True)
def _(mo):
    mo.md("""
    # Dividend Estimates

    Trying to reconstruct historical dividend yields from beancount is complicated and error-prone. Some of the issues:

    1. Simply linking up the dividend with the security is not explicit in beancount. Even if you have an account *Income:Dividends:VTI* for each fund you are still relying on the heuristic of the account name being the same as the security name. What if they aren't the same?
    2. Even if you can associate a dividend and security, getting the balance of that security via BQL is not easy. I don't think there's a simple way to do it in one query, so you're probably left iterating over things and calling BQL multiple times. As some point one beings to wonder if simply dropping into Python would be easier.
    3. But even if you solve that, it is still error-prone because you almost certainly didn't capture the ex-div date in Beancount (as an Account-Receivable?) and only captured the actual payment date. How many shares did you own on the ex-div date...when you don't know when that was? What if you sell shares between the ex-div and payment date? What if there is a lengthy period between the ex-div date and the payment? This is the case with VEU on the ASX (Australia) which has a 1-month lag. This lag also complicates things because conceptually you want to measure things based on the ex-div (which you didn't capture in Beancount!). For instance, the payment in January is actually the Q4 dividend, no some kind of Q1 dividend. So you'd need special case code to handle all of that anyway?


    So...just store it explicity in a beancount event:

    ```
    2025-12-31 event "dividend" "MFDX: 0.33"
    ```
    """)
    return


@app.cell(disabled=True)
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
        account in (select account from #accounts where open.meta['include_in_dash'] = 'true')
    """)

    # the column names are 'units (VTI)' and we just want 'VTI'
    _df = _df.rename(lambda c: c.replace('units (', '')).rename(lambda c: c.replace(')', ''))

    # Want the name to match what we capture in the events table.
    # Note that VEU's dividends are tracked in USD.
    holdings = _df.rename({'VEU_AX': 'VEU'})
    return (holdings,)


@app.cell
def _(holdings, math, mo, pl, run_query, today):
    _df = run_query(f"""
    select date,description from #events where type = 'dividend'
    """)
    _df = _df.with_columns(pl.col("description").str.split_exact(':', 1))
    _df = _df.with_columns(pl.col("description").struct.rename_fields(['etf', 'dividend'])).unnest('description')
    _df = _df.with_columns(pl.col('dividend').str.strip_chars())
    _df = _df.with_columns(pl.col('dividend').cast(pl.Decimal(10, 6)))
    _df = _df.with_columns(pl.col('date').dt.quarter().alias('q'))

    # we may need to massage some of the Quarters.
    # If their ex-div date is very close to the end of a quarter (e.g. December 30)
    # then the actual pay date recorded in beancount may be in the following quarter (e.g. January 3)
    # So for anything date whose Month is 1, 4, 7, 10 we use the previous quarter.
    # That is: January payments become Q4 dividends, April payments become Q2 dividends, and so on.
    _df = _df.with_columns(pl.when(pl.col('date').dt.month().is_in([1, 4, 7, 10]))
                    .then(pl.col('q') - 1)
                    .otherwise(pl.col('q')))

    # only use the most recent 2 years (8 quarters)
    _df = _df.sort('date', descending=True).group_by('etf').tail(8)

    # This gets the average dividend for each quarter for each ETF
    _df = _df.group_by('etf', 'q').mean()

    # we need to transpose it so we can join to it
    _hold = holdings.transpose(include_header=True, column_names=['holding']).rename({'column': 'etf'})

    _df = _df.join(_hold, on='etf')
    _df = _df.with_columns(pl.col('dividend').mul(pl.col('holding')).alias('div_amt'))

    estimated_dividends = _df.group_by('q').agg(pl.col('div_amt').sum())

    todays_quarter = math.floor((today.month - 1) / 3) + 1
    _div_next_q = estimated_dividends.filter(pl.col('q') == todays_quarter)['div_amt'].item()
    _div_annual = estimated_dividends.sum()['div_amt'].item()

    mo.hstack([mo.md('# Estimated Dividends'),
              mo.md(f"Next Q{todays_quarter}: ${_div_next_q:,.0f}").style(),
              mo.md(f"Year: ${_div_annual:,.0f}").style()])
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


@app.cell
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
    return (
        Decimal,
        datetime,
        home_dir,
        load_file,
        math,
        mo,
        pl,
        pmt,
        pn,
        printer,
        pv,
        run_bql_query,
    )


@app.cell
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
