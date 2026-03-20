import marimo

__generated_with = "0.21.1"
app = marimo.App(width="medium")


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
    import beancount.core.prices

    import datetime
    from pathlib import Path
    import math

    from numpy_financial import pmt, pv

    import summator
    import life_expectancy

    home_dir = Path.home()
    today = datetime.date.today()
    return (
        alt,
        beancount,
        datetime,
        home_dir,
        life_expectancy,
        load_file,
        mo,
        pl,
        pmt,
        printer,
        pv,
        run_bql_query,
        summator,
        today,
    )


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
def _(home_dir):
    beancount_file = f'{home_dir}/Documents/beancount/my.bean'
    return (beancount_file,)


@app.cell
def _(beancount_file, load_file, printer):
    entries, _errors, options = load_file(beancount_file)
    printer.print_errors(_errors)
    return entries, options


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
def _(datetime, today):
    # Which accounts to include when calculating "liquid net worth"
    account_re = 'Assets:US:Schwab:Brokerage|Assets:US:Vanguard|Assets:US:Interactive-Brokers|Assets:AUS:First-State-Super'
    # convert everything to a single currency
    CURRENCY = 'AUD'

    # All calculations are based on these dates. We're just doing the current year.
    start_date = datetime.date(datetime.date.today().year, 1, 1)
    end_date = datetime.date.today()

    age_1 = today.year - 1975
    age_2 = today.year - 1990
    return CURRENCY, account_re, age_1, age_2, end_date, start_date


@app.cell
def _(datetime, pl):
    def get_days_in_year():
        current_year = datetime.date.today().year
        days_in_year = (
            (pl.date(current_year + 1, 1, 1) - pl.date(current_year, 1, 1))
            .dt.total_days())
        return days_in_year

    # This INCLUDES the end date.
    def daterange(start_date: datetime.date, end_date: datetime.date):
        days = int((end_date - start_date).days)
        for n in range(days + 1):
            yield start_date + datetime.timedelta(n)

    return daterange, get_days_in_year


@app.cell
def _(mo, pl, run_query, today):
    # We can check to make sure the beancount price_map is reasonably up to date (i.e. within 5 days)
    _df = run_query(f"""
        select * from #prices;
    """)

    _recent = _df.sort('date').group_by('currency').last()
    _stale = _recent.filter(pl.col('date') < today - pl.duration(days=5))

    # get the list of current holdings and compare them against this stale list

    # beancount returns anything we've ever held (just with a 0 quantity).
    # we only care about current holdings so strip out anything with 0 quantity.
    _holdings = run_query(f"""
    select
        sum(number) as units,
        currency
    group by currency
    """).filter(pl.col('units') > 0)

    _stale_currencies = _stale.join(_holdings, on='currency')['currency']

    # These are things we know don't update frequently, so exclude them.
    _ignore = ['VND', 'HOUSE_VN_DBP', 'HOUSE_AUS_HAY']

    _s = _stale_currencies.filter(~_stale_currencies.is_in(_ignore))
    _str = _s.str.join(delimiter='\n- ').item()

    mo.md(f"""/// Attention | Stale price data.
    - {_str}
    """) if not _s.is_empty() else None
    return


@app.cell
def _(CURRENCY, beancount, daterange, entries, options, pl, summator):
    def get_nws(start_date, end_date, account_re):
        summer = summator.BeanSummator(entries, options, account_re)

        price_map = beancount.core.prices.build_price_map(entries)

        nws = {'date': [], 'net_worth': []}

        for d in daterange(start_date, end_date):
            sum = summer.sum_till_date(d)
            nws['date'].append(d.isoformat())
            nws['net_worth'].append(sum.convert(CURRENCY, price_map, d).sum_all().get_currency_units(CURRENCY).number)

        return pl.DataFrame(nws, schema={'date': pl.Date, 'net_worth': pl.Float64})

    return (get_nws,)


@app.cell
def _(datetime, mo, pl, today):
    # To calculate PMT we need number of periods (i.e. life expectancy), expected returns, and bequest

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

    mo.md(""" /// Attention | Expected returns only valid for 2026. Update them!
    """) if today.year != 2026 else None
    return (build_expected_returns_dataframe,)


@app.cell
def _(age_1, age_2, life_expectancy):
    life = life_expectancy.get_conservative_life_expectancy(
        life_expectancy.male, age_1,
        life_expectancy.female, age_2
    )
    return (life,)


@app.cell
def _():
    bequest = 0
    return (bequest,)


@app.cell
def _(
    account_re,
    bequest,
    build_expected_returns_dataframe,
    end_date,
    get_nws,
    life,
    pl,
    pmt,
    start_date,
):
    _nw = get_nws(start_date, end_date, account_re)

    _rates = build_expected_returns_dataframe()

    pmts = -pmt(rate = _rates['rate'],
        nper = life,
        fv = bequest,
        pv = _nw['net_worth'],
        when='begin')

    raw_pmt = _nw.with_columns(pmt = pmts,
                               day_of_year = pl.col('date').dt.ordinal_day(),
                               nper = pl.lit(life),
                               rate = _rates['rate'])
    return (raw_pmt,)


@app.cell
def _(pl, pv):
    # We can 'tilt' the resulting PMT calculation towards either portfolio stability or income stability.

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

    def tilt_income_target(pmt):
        target_income = 225_000
        tilt = -0.5
        target = pv(pmt['rate'], pmt['nper'], -target_income, 0)
        return tilt_portfolio(pmt.with_columns(target = target), tilt)

    return tilt_income_target, tilt_portfolio_target


@app.cell
def _(get_days_in_year, pl):
    # Given annual PMT amount, calculate both a daily spend
    # as well a cumulative spend up to the current day. We will
    # use that to compare against our actual spending.

    def calculate_spend(pmt):
        pmt = pmt.with_columns(daily_spend = pl.col('pmt') / get_days_in_year())
        pmt = pmt.with_columns(target = pl.col('daily_spend') * pl.col('day_of_year'))
        return pmt

    return (calculate_spend,)


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
    return (income_ytd,)


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
    return (spending_ytd,)


@app.cell
def _(
    alt,
    calculate_spend,
    mo,
    raw_pmt,
    tilt_income_target,
    tilt_portfolio_target,
):
    def chart_tilts(raw, portfolio, income): 
        _j = raw.select(['date', 'pmt']).join(
        portfolio.select(['date', 'pmt']), on='date', suffix='_portfolio_tilt').join(
        income.select(['date', 'pmt']), on='date', suffix='_income_tilt').rename({
            'pmt': 'Raw',
            'pmt_income_tilt': 'Income',
            'pmt_portfolio_tilt': 'Portfolio'
        })

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
                     alt.Tooltip('Raw:Q', title='PMT', format='$,.0f'),
                     alt.Tooltip('Income:Q', title='Income Tilt', format='$,.0f'),
                     alt.Tooltip('Portfolio:Q', title='Portfolio Tilt', format='$,.0f')]
        ).add_params(hover).properties(width='container', title='Withdrawals')

        return chart + tooltips
    
    mo.ui.altair_chart(chart_tilts(calculate_spend(raw_pmt),
                                  calculate_spend(tilt_portfolio_target(raw_pmt)),
                                  calculate_spend(tilt_income_target(raw_pmt))))
    return


@app.cell
def _(
    calculate_spend,
    income_ytd,
    pl,
    raw_pmt,
    spending_ytd,
    tilt_income_target,
    tilt_portfolio_target,
):
    def build_trends(raw, portfolio, income):
        trend = calculate_spend(raw).select(['date', 'target'])
    
        trend = trend.join(portfolio.select(['date', 'target']), on='date', suffix='_portfolio_tilt')
        trend = trend.join(income.select(['date', 'target']), on='date', suffix='_spending_tilt')
        trend = trend.with_columns(tilt = pl.min_horizontal(pl.col('target_portfolio_tilt'),
                                     pl.col('target_spending_tilt')))
    
        trend = trend.join(income_ytd.select(['date', 'income']), on='date', how='left')
        trend = trend.join(spending_ytd.select(['date', 'spending']), on='date', how='left')

        # Income and Spending don't necessarily happen on every day (especially Income)
        # so the resulting join will have nulls that we need to fill in correctly.
        return trend.fill_null(strategy='forward').fill_null(0)

    def build_spending_trends():
        return build_trends(calculate_spend(raw_pmt),
                calculate_spend(tilt_portfolio_target(raw_pmt)),
                calculate_spend(tilt_income_target(raw_pmt)))

    return (build_spending_trends,)


@app.cell
def _(build_spending_trends, pl):
    def build_progress():
        # First we want to track against tilted-PMT without considering income. This is our "safest scenario" -- if we dropped our bonus income to $0 how would we be going?
    
        trend = build_spending_trends()
        trend = trend.with_columns(pl.col('tilt').sub(pl.col('spending')).alias('tilt_trend'))
    
        # next we want to look at tilted-PMT but add in the bonus income
    
        trend = trend.with_columns(pl.col('tilt').sub(pl.col('spending')).add(pl.col('income')).alias('tilt_income_trend'))
    
        # finally we want to look at our "upper limit" ... drop the tilt, just use raw PMT
        # but also include bonus income
    
        trend = trend.with_columns(pl.col('target')
            .sub(pl.col('spending'))
            .add(pl.col('income'))
            .alias('notilt_income_trend'))
    
        delta_trend = trend.select(pl.col('date'),
                                     pl.col('tilt_trend'),
                                     pl.col('tilt_income_trend'),
                                     pl.col('notilt_income_trend'))
        return delta_trend.sort('date', descending=True)

    build_progress()
    return (build_progress,)


@app.cell
def _(alt, build_progress, mo):
    def chart_spending(trend):
        source = trend.rename({
            'tilt_trend': 'Tilt',
            'tilt_income_trend': 'Tilt + Income',
            'notilt_income_trend': 'No Tilt + Income'
        }).unpivot(index='date').sort('date')
    
        hover = alt.selection_point(fields=['date'], nearest=True, on='mouseover', empty=False)
    
        chart = alt.Chart(source).mark_line(point=True).encode(
            x=alt.X('date', title='Date'),
            y=alt.Y('value', title='Difference'),
            color=alt.Color('variable',
                            title='Method')).properties(width='container')
    
        tooltips = alt.Chart(source).transform_pivot(
            'variable',
            value='value',
            groupby=['date']).mark_rule().encode(
            x='date:T',
            opacity=alt.condition(hover, alt.value(0.3), alt.value(0)),
            tooltip=[alt.Tooltip('date:T', title='Date'),
                     alt.Tooltip('Tilt:Q',
                                 format='$,.0f'),
                     alt.Tooltip('Tilt + Income:Q',
                                 format='$,.0f'),
                     alt.Tooltip('No Tilt + Income:Q',
                                 format='$,.0f')]
        ).add_params(hover)
    
        max_point = alt.Chart(source).transform_window(
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
        text = max_point.mark_text(dx=-50, dy=3, fontWeight='bold').encode(
            x='date:T',
            y='value:Q',
            text=alt.Text('value:Q', format='$,.0f')
        )

        return chart + tooltips + text

    mo.ui.altair_chart(chart_spending(build_progress()))
    return


if __name__ == "__main__":
    app.run()
