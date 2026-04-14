import marimo

__generated_with = "0.23.0"
app = marimo.App(width="medium")


@app.cell
def _():
    # This has tons of assumptions embedded in it for my own personal usage.
    # It won't work on any of the example beancount files. But you can look
    # through it as an example of an overly complicated real-world usage.
    return


@app.cell
def _(beancount_loader_errors, mo, printer):
    # Sanity check our beancount file.
    # Does everything have a payee? (./problems.sh)
    # Is all the vacation spending in a leaf-account?
    # Are there any flagged transactions?

    mo.md(f"""
    {printer.print_errors(beancount_loader_errors)}
    """) if beancount_loader_errors else None
    return


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
def _(run_query):
    _p = run_query(f"""
    select
        flag, payee, filename, lineno, sum(convert(position, 'AUD', date)) as spent
    where
        year = year(today())
        and payee is NULL
        and flag != 'P'
    order by
        lineno asc
    """)

    _p if not _p.is_empty() else None
    return


@app.cell
def _(calculate_spend, min_pmt, mo, pl, spending_ytd, today):
    _df = calculate_spend(min_pmt).join(
        spending_ytd,
        on='date',
        how='left').sort('date').fill_null(strategy='forward').fill_null(0).with_columns(
        pl.col('spending') / pl.col('pmt') * 100)

    _doy = int(today.timetuple().tm_yday / 365 * 100)
    _spend = int(_df['spending'].last())

    if _doy >= _spend:
        _style = 'green'
    else:
        _style = 'red'

    mo.hstack((mo.md(f'# {today}'),
                mo.md(f"Tilt: {_spend}%").style(color=_style),
                mo.md(f"Date: {_doy}%").style(color='grey')))
    return


@app.cell
def _(alt, build_progress, mo):
    def _chart_spending(trend):
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
        text = max_point.mark_text(dx=-30, dy=25, fontWeight='bold', fontSize=14).encode(
            x='date:T',
            y='value:Q',
            text=alt.Text('value:Q', format='$,.0f')
        )

        return chart + tooltips + text

    mo.ui.altair_chart(_chart_spending(build_progress()))
    return


@app.cell
def _(estimate_spending, min_pmt, pn, raw_pmt, spending_ytd):
    def _make_indicators():
        def get_last(df, field):
            n = df.sort('date')[field].last()
            return round(int(n), -3)

        ytd = pn.indicators.Number(
            name = 'YTD Spend',
            value = spending_ytd['spending'].last(),
            format = '${value:,.0f}',
            colors = [(0, 'red'), (500_000, 'green')]
        )

        projected = pn.indicators.Number(
            name = 'Projected Spend',
            value = estimate_spending(spending_ytd),
            format = '${value:,.0f}',
            colors = [(0, 'white'), (500_000, 'grey')]
        )

        tiltpmt = pn.indicators.Number(
            name = 'Tilt PMT',
            value = get_last(min_pmt, 'pmt'),
            format = '${value:,.0f}',
            colors = [(0, 'red'), (500_000, 'green')]
        )

        rawpmt = pn.indicators.Number(
            name = 'Raw PMT',
            value = get_last(raw_pmt, 'pmt'),
            format = '${value:,.0f}',
            colors = [(0, 'white'), (500_000, 'grey')]
        )

        return (ytd, projected, tiltpmt, rawpmt)

    pn.GridBox(*_make_indicators(), ncols=2)
    return


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
def _(
    CURRENCY,
    beancount,
    beancount_entries,
    beancount_options,
    daterange,
    pl,
    summator,
):
    def get_nws(start_date, end_date, account_re):
        summer = summator.BeanSummator(beancount_entries, beancount_options, account_re)

        price_map = beancount.core.prices.build_price_map(beancount_entries)

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

        # Feb-23-2026 lowered the expected returns from 3.2 to 3.1, so reflect that here.
        # Apr-7-2026 lowered from 3.1 to 3.0, should be the final value, I think.    
        # this also shows how you could (in theory) have a more dynamic expected returned
        # e.g. 1/CAPE10 calculated monthly
        df = df.with_columns(
            rate = pl.when(pl.col("date") < datetime.date(2026, 2, 23))
            .then(pl.lit(0.032))
            .when(pl.col("date") < datetime.date(2026, 4, 1))
            .then(pl.lit(0.031))
            .otherwise(pl.lit(0.030))
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
def _(pl, pv, raw_pmt):
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

    # 7-Apr-2026: Set income to 150_000
    # That seems roughly what our steady-state spending is
    # (minus vacation and other expenses like that)
    # Using this as a target seems to make more sense than
    # some arbitrary big number
    def target_from_income(pmt):
        target_income = 150_000 #250_000
        target = pv(pmt['rate'], pmt['nper'], -target_income, fv=0, when='begin')
        return target

    def tilt_income_target(pmt):
        tilt = -0.5
        target = target_from_income(pmt)
        return tilt_portfolio(pmt.with_columns(target = target), tilt)

    # We want to find the minimum of the portfolio tilt and the income tilt
    _df1 = tilt_portfolio_target(raw_pmt)
    _df2 = tilt_income_target(raw_pmt)

    min_pmt = _df1.with_columns(
        pmt = pl.min_horizontal('pmt', _df2['pmt'])
    )
    return (
        min_pmt,
        target_from_income,
        tilt_income_target,
        tilt_portfolio_target,
    )


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
            y=alt.Y('value', title='Amount $').scale(domainMin=150_000),
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

    #build_progress()
    return (build_progress,)


@app.cell
def _(
    account_re,
    alt,
    end_date,
    get_nws,
    mo,
    pl,
    raw_pmt,
    start_date,
    target_from_income,
):
    # This shows us how much "extra" we have for large capital purchases
    def calculate_excess():
        return get_nws(start_date, end_date, account_re).with_columns(
            target = target_from_income(raw_pmt)
        ).with_columns(
            excess = pl.col('net_worth') - pl.col('target')
        ).select(pl.col('date'), pl.col('excess'))

    def _chart_excess():
        source = calculate_excess()
        hover = alt.selection_point(fields=['date'], nearest=True, on='mouseover', empty=False)

        tooltips = alt.Chart(source).mark_rule().encode(
            x='date:T',
            opacity=alt.condition(hover, alt.value(0.3), alt.value(0)),
            tooltip=[alt.Tooltip('date:T', title='Date'),
                     alt.Tooltip('excess', title='Excess', format='$,.0f')]).add_params(hover).properties(width='container')

        chart = alt.Chart(source).mark_line().encode(
            x = 'date',
            y = 'excess'
        ).properties(title='Excess Portfolio')

        return chart + tooltips

    mo.ui.altair_chart(_chart_excess())
    return


@app.cell
def _(bequest, pl, pmt, raw_pmt, tilt_income_target):
    n_rows = 20
    step = 100_000

    _rounded = raw_pmt.tail(1).with_columns((pl.col('net_worth') / 100_000).floor() * 100_000)

    _df = _rounded.select([pl.col('nper').first(), pl.col('rate').first(),
        (pl.col('net_worth') - pl.int_range(0, n_rows) * step).alias('net_worth')
    ])

    _pmts = -pmt(rate = _df['rate'],
        nper = _df['nper'],
        fv = bequest,
        pv = _df['net_worth'],
        when='begin')
    _raw_pmt = _df.with_columns(pmt = _pmts)
    _tilt = tilt_income_target(_raw_pmt)

    #_tilt.filter(pl.col('net_worth') > pl.col('target'))
    return


@app.cell
def _(datetime, pl, run_query, today):
    # Estimate our projected spending for the year based on past expenses
    # and what we've spent so far this year.

    def estimate_spending(spend_df):
        ytd_spend = spend_df.sort('date')['spending'].last()

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
        estimate = (ytd_spend + remainder)

        s = estimate.select(pl.nth(0)).to_series().last()
        return round(int(s), -3)

    #estimate_spending()
    return (estimate_spending,)


@app.cell
def _(datetime, get_holdings, math, mo, pl, run_query, today):
    def build_dividends():
        df = run_query(f"""
        select date,description from #events where type = 'dividend'
        """)
        df = df.with_columns(pl.col("description").str.split_exact(':', 1))
        df = df.with_columns(pl.col("description").struct.rename_fields(['etf', 'dividend'])).unnest('description')
        df = df.with_columns(pl.col('dividend').str.strip_chars())
        df = df.with_columns(pl.col('dividend').cast(pl.Decimal(10, 6)))
        df = df.with_columns(pl.col('date').dt.quarter().alias('q'))

        # we may need to massage some of the Quarters.
        # If their ex-div date is very close to the end of a quarter (e.g. December 30)
        # then the actual pay date recorded in beancount may be in the following quarter (e.g. January 3)
        # So for anything date whose Month is 1, 4, 7, 10 we use the previous quarter.
        # That is: January payments become Q4 dividends, April payments become Q2 dividends, and so on.
        df = df.with_columns(pl.when(pl.col('date').dt.month().is_in([1, 4, 7, 10]))
                        .then(pl.col('q') - 1)
                        .otherwise(pl.col('q')))

        return df

    # This will create an annual average. So if you specify exactly one year,
    # then it is the actual dividends for that 12 month range. But if you specify
    # 24 months it will be the 12-month average.
    def calc_dividends(start, end):
        df = build_dividends().filter(pl.col('date').is_between(start, end)).group_by('etf', 'q').mean()

        hold = get_holdings().transpose(include_header=True, column_names=['holding']).rename({'column': 'etf'})

        df = df.join(hold, on='etf')
        df = df.with_columns(pl.col('dividend').mul(pl.col('holding')).alias('div_amt'))
        return df.group_by('q').agg(pl.col('div_amt').sum())

    todays_quarter = math.floor((today.month - 1) / 3) + 1

    # this isn't actually the start of the quarter. we really mean
    # "a little before the next quarter starts" so we capture any
    # dividends that show up days/weeks late
    divs_payable = datetime.date(today.year, ((todays_quarter - 1) * 3) + 3, 1)
    prev_divs_payable = pl.DataFrame({"date": [divs_payable]}).with_columns(pl.col('date').dt.offset_by('-3mo')).item()

    # The start and end dates a little tricky because of when dividends actually arrive: sometimes
    # a few days after the quarter has technically ended
    _1yr_ago = calc_dividends(
        pl.lit(today).dt.offset_by('-25mo'),
        pl.lit(today).dt.offset_by('-13mo')
    )

    _2yr_avg = calc_dividends(
        pl.lit(today).dt.offset_by('-25mo'),
        divs_payable
    )

    _current_yr = calc_dividends(
        pl.lit(today).dt.offset_by('-13mo'),
        divs_payable
    )

    _prev_qtr = calc_dividends(
        prev_divs_payable,
        divs_payable
    )

    _est = _2yr_avg

    _div_next_q = _est.filter(pl.col('q') == todays_quarter)['div_amt'].item()
    _div_annual = _est.sum()['div_amt'].item()

    _green_up = mo.icon('lucide:arrow-big-up', color='green', size=24)
    _red_down = mo.icon('lucide:arrow-big-down', color='red', size=24)

    # This calculates the annual change in our dividends
    _change = (_current_yr.sum() / _1yr_ago.sum() - 1)['div_amt'].item()
    if _change > 0:
        _delta = mo.md(f"""{_green_up}{100 * _change:,.1f}%""")
    else:
        _delta = mo.md(f"""{_red_down} {100 * _change:,.1f}%""")

    mo.hstack([mo.md('# Estimated Dividends (USD)'),
               _delta,
               mo.md(f"Next Q{todays_quarter}: ${_div_next_q:,.0f}").style(),
               mo.md(f"Year: ${_div_annual:,.0f}").style()], align='center')
    return


@app.cell
def _(run_query):
    def get_holdings():
        df = run_query(f"""
    SELECT
        units(sum(position)) as units
    WHERE
        account in (select account from #accounts where open.meta['include_in_dash'] = 'true')
    """)

        # the column names are 'units (VTI)' and we just want 'VTI'
        df = df.rename(lambda c: c.replace('units (', '')).rename(lambda c: c.replace(')', ''))

        # Want the name to match what we capture in the events table.
        # Note that VEU's dividends are tracked in USD.
        return df.rename({'VEU_AX': 'VEU'})

    return (get_holdings,)


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
        math,
        mo,
        pl,
        pmt,
        pn,
        printer,
        pv,
        run_bql_query,
        summator,
        today,
    )


@app.cell
def _(home_dir):
    beancount_file = f'{home_dir}/Documents/beancount/my.bean'
    return (beancount_file,)


@app.cell
def _(beancount_file, load_file):
    beancount_entries, beancount_loader_errors, beancount_options = load_file(beancount_file)
    return beancount_entries, beancount_loader_errors, beancount_options


@app.cell
def _(beancount_entries, beancount_options, pl, run_bql_query):
    def run_query(query):
        """ Convert a beancount BQL query result to a polars dataframe """
        cols, rows = run_bql_query(beancount_entries, beancount_options, query, numberify=True)
        schema = [k.name for k in cols]
        df = pl.DataFrame(schema=schema, data=rows, orient='row', infer_schema_length=None)
        return df

    return (run_query,)


if __name__ == "__main__":
    app.run()
