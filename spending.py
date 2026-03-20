import marimo

__generated_with = "0.21.1"
app = marimo.App()


@app.cell
def _(alt, end_date, mo, networth, start_date):
    mo.ui.altair_chart(alt.Chart(networth).mark_line(point=True)
        .encode(x=alt.X('date', title='Date'),
                y=alt.Y('net_worth', title='Net Worth', axis=alt.Axis(format='$,.0f')).scale(domainMin=5_500_000),
                tooltip=[alt.Tooltip('date', title='Date'), alt.Tooltip('net_worth', title='Net worth', format='$,.0f')])
        .properties(title=alt.Title('Net Worth',
                                    subtitle=f"{start_date} to {end_date}"),
                   width='container'))
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
def _(datetime, pl):
    def get_days_in_year():
        current_year = datetime.date.today().year
        days_in_year = (
            (pl.date(current_year + 1, 1, 1) - pl.date(current_year, 1, 1))
            .dt.total_days())
        return days_in_year

    return (get_days_in_year,)


@app.cell
def _(nws, pl):
    from numpy_financial import pmt, pv

    _nw = pl.DataFrame(nws, schema={'date': pl.Date, 'net_worth': pl.Decimal(scale=2)})
    _nw = _nw.with_columns(rate = pl.lit(0.031))
    _nw = _nw.with_columns(nper = pl.lit(72.335))
    _nw = _nw.with_columns(fv = pl.lit(0))
    _nw = _nw.with_columns(pl.col('net_worth').cast(float))

    pmts = -pmt(rate=_nw['rate'],
                nper=_nw['nper'],
                pv=_nw['net_worth'],
                fv=_nw['fv'],
                when='begin')

    _nw = _nw.with_columns(pl.Series('pmt', pmts, dtype=pl.Decimal(scale=2)))
    _nw = _nw.with_columns(day_of_year = pl.col('date').dt.ordinal_day())

    networth = _nw
    networth
    return networth, pv


@app.cell
def _(get_days_in_year, networth, pl):
    def calculate_spend(pmt):
        pmt = pmt.with_columns(daily_spend = pl.col('pmt') / get_days_in_year())
        pmt = pmt.with_columns(target = pl.col('daily_spend') * pl.col('day_of_year'))
        return pmt
    calculate_spend(networth)
    return (calculate_spend,)


@app.cell
def _(calculate_spend, networth, pl, pv):
    def tilt_portfolio(df, tilt_amt):
        df = df.with_columns(target_frac = pl.col('net_worth') / pl.col('target'))
        df = df.with_columns(tilt_factor = pl.col('target_frac').pow(tilt_amt))
        df = df.with_columns(pmt = pl.col('pmt') * pl.col('tilt_factor'))
        df = df.with_columns(pl.col('pmt').cast(pl.Decimal(scale=2)))

        return df

    def tilt_portfolio_target(df):
        tilt = 0.5
        target = 7_000_000
        return tilt_portfolio(df.with_columns(target = pl.lit(target)), tilt)

    def tilt_spend_target(pmt):
        target_income = 225_000
        tilt = -0.5
        target = pv(pmt['rate'], pmt['nper'], -target_income, 0)
        return tilt_portfolio(pmt.with_columns(target = target), tilt)

    raw = calculate_spend(networth)
    port_tilt = calculate_spend(tilt_portfolio_target(networth))
    income_tilt = calculate_spend(tilt_spend_target(networth))

    tilt_portfolio_target(networth)
    return income_tilt, port_tilt, raw


@app.cell
def _(alt):
    @alt.theme.register('dash_theme', enable=True)
    def my_theme():
        return {
            'config': {
                'font': 'Spartan League',
                'background': '#f9f9f9',
            }
        }

    return


@app.cell
def _(alt, income_tilt, mo, port_tilt, raw):
    _j = raw.select(['date', 'pmt']).join(
        port_tilt.select(['date', 'pmt']), on='date', suffix='_portfolio_tilt').join(
        income_tilt.select(['date', 'pmt']), on='date', suffix='_income_tilt')

    hover = alt.selection_point(fields=['date'], nearest=True, on='mouseover', empty=False)

    source = _j.unpivot(index='date')

    chart = alt.Chart(source).mark_line(point=True).encode(
        x='date',
        y=alt.X('value', title='Amount $').scale(domainMin=150_000),
        color='variable')

    tooltips = alt.Chart(source).transform_pivot(
        'variable', value='value', groupby=['date']
    ).mark_rule().encode(
        x='date:T',
        opacity=alt.condition(hover, alt.value(0.3), alt.value(0)),
        tooltip=[alt.Tooltip('date:T', title='Date'),
                 alt.Tooltip('pmt:Q', title='PMT', format='$,.0f'),
                 alt.Tooltip('pmt_income_tilt:Q', title='Income Tilt', format='$,.0f'),
                 alt.Tooltip('pmt_portfolio_tilt:Q', title='Portfolio Tilt', format='$,.0f')]
    ).add_params(hover).properties(width='container', title='Withdrawals')

    mo.ui.altair_chart(chart + tooltips)
    return (hover,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Income

    Income from these three specific categories are a "bonus" above and beyond what the portfolio can generate. Conceptually they can be subtracted from spending to show how much room we still have left towards our portfolio PMT spending limit.
    """)
    return


@app.cell
def _(datetime, pl, run_query):
    income_ytd = run_query(f"""
    select
        date,
        sum(convert(cost(position), 'AUD', date)) as amount
    where
        year = {datetime.date.today().year}
        and (account = 'Income:Salary' or account = 'Income:Rent' or account = 'Income:Interest:SecuritiesLending')
    group by date
    """).with_columns(pl.col('amount (AUD)').abs(), pl.col('amount (AUD)').abs().cum_sum().alias('income'))

    income_ytd
    return (income_ytd,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Spending

    This is just a simple tracking of our expenses.
    """)
    return


@app.cell
def _(datetime, pl, run_query):
    spending_ytd = run_query(f"""
    select
        date,
        sum(convert(cost(position), 'AUD', date)) as amount
    where
        account ~ 'Expenses:'
        and year = {datetime.date.today().year}
    group by date
    """).with_columns(pl.col('amount (AUD)').cum_sum().alias('spending'))

    spending_ytd
    return (spending_ytd,)


@app.cell
def _(income_tilt, income_ytd, pl, port_tilt, raw, spending_ytd):
    trend = raw.select(['date', 'target'])

    trend = trend.join(port_tilt.select(['date', 'target']), on='date', suffix='_portfolio_tilt')
    trend = trend.join(income_tilt.select(['date', 'target']), on='date', suffix='_spending_tilt')
    trend = trend.with_columns(tilt = pl.min_horizontal(pl.col('target_portfolio_tilt'),
                                 pl.col('target_spending_tilt')))

    trend = trend.join(income_ytd.select(['date', 'income']), on='date')
    trend = trend.join(spending_ytd.select(['date', 'spending']), on='date')

    #trend
    return (trend,)


@app.cell
def _(pl, trend):
    # First we want to track against tilted-PMT without considering income. This is our "safest scenario" -- if we dropped our bonus income to $0 how would we be going?

    _trend = trend.with_columns(pl.col('tilt').sub(pl.col('spending')).alias('tilt_trend'))

    # next we want to look at tilted-PMT but add in the bonus income

    _trend = _trend.with_columns(pl.col('tilt').sub(pl.col('spending')).add(pl.col('income')).alias('tilt_income_trend'))

    # finally we want to look at our "upper limit" ... drop the tilt, just use raw PMT
    # but also include bonus income

    _trend = _trend.with_columns(pl.col('target').sub(pl.col('spending')).add(pl.col('income')).alias('notilt_income_trend'))

    delta_trend = _trend.select(pl.col('date'),
                                 pl.col('tilt_trend'),
                                 pl.col('tilt_income_trend'),
                                 pl.col('notilt_income_trend'))
    delta_trend.sort('date', descending=True)

    # Why is this missing so much data? Should have daily numbers in here?
    # it doesn't even have TODAY?!
    return (delta_trend,)


@app.cell
def _(alt, delta_trend, hover, mo):
    _source = delta_trend.unpivot(index='date').sort('date')

    _hover = alt.selection_point(fields=['date'], nearest=True, on='mouseover', empty=False)

    _chart = alt.Chart(_source).mark_line(point=True).encode(
        x=alt.X('date', title='Date'),
        y=alt.Y('value', title='Difference'),
        color=alt.Color('variable',
                        title='Method')).properties(width='container')

    _tooltips = alt.Chart(_source).transform_pivot(
        'variable',
        value='value',
        groupby=['date']).mark_rule().encode(
        x='date:T',
        opacity=alt.condition(hover, alt.value(0.3), alt.value(0)),
        tooltip=[alt.Tooltip('date:T', title='Date'),
                 alt.Tooltip('tilt_trend:Q',
                             title='Tilt',
                             format='$,.0f'),
                 alt.Tooltip('tilt_income_trend:Q',
                             title='Tilt + Income',
                             format='$,.0f'),
                 alt.Tooltip('notilt_income_trend:Q',
                             title='No Tilt + Income',
                             format='$,.0f')]
    ).add_params(_hover)

    _max_point = alt.Chart(_source).transform_window(
        row_number = 'rank()',
        sort = [alt.SortField('date', order='descending')]
    ).transform_filter(
        alt.datum.row_number == 1
    )

    # 3. Layer the Arrow (using dy to offset it above the point)
    #_arrow = _max_point.mark_text(text='↓', fontSize=30, dy=-20).encode(
    #    x='date:T', y='value:Q'
    #)

    # 4. Layer the Text Label
    _text = _max_point.mark_text(dx=-50, dy=3, fontWeight='bold').encode(
        x='date:T',
        y='value:Q',
        text=alt.Text('value:Q', format='$,.0f')
    )

    mo.ui.altair_chart(_chart + _tooltips + _text)
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
