# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "altair>=6.0.0",
#     "beancount>=3.2.0",
#     "beanquery>=0.2.0",
#     "great-tables>=0.21.0",
#     "marimo>=0.20.4",
#     "polars>=1.39.0",
#     "python-dateutil>=2.9.0.post0",
#     "requests>=2.32.0",
# ]
# ///

import marimo

__generated_with = "0.20.4"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""/// Attention | Edit this to point to your beancount file if you want to try on real data.""") if mo.app_meta().mode == 'edit' else None
    return


@app.cell
def _():
    #beancount_file = f'{home_dir}/Documents/beancount/my.bean'
    beancount_file = 'huge-example.beancount'
    return (beancount_file,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Quickest demo

    This is just a quick example to show you what running a BQL-query and displaying it in Morimo natively looks like with no extra effort required.
    """)
    return


@app.cell(hide_code=True)
def _(mo, run_query):
    _bql = """select year,month order by date"""
    _df = run_query(_bql)

    year_slider = mo.ui.range_slider(
        start=_df[0]['year'].item(),
        stop=_df[-1]['year'].item(),
        full_width=True)
    return (year_slider,)


@app.cell(hide_code=True)
def _(mo, year_slider):
    start_year = year_slider.value[0]
    end_year = year_slider.value[1]
    mo.vstack([mo.md(f"Years selected to query: {start_year} - {end_year}"), year_slider])
    return end_year, start_year


@app.cell(hide_code=True)
def _(end_year, run_query, start_year):
    _bql = f"""select * where account ~ 'Income' and year >= {start_year} and year <= {end_year}"""
    run_query(_bql)
    return


@app.cell(hide_code=True)
def _(mo):
    group_by = mo.ui.dropdown(['Year', 'Quarter', 'Month', 'Week'], label='Choose reporting grouping.', value='Month')
    group_by
    return (group_by,)


@app.cell(hide_code=True)
def _(alt, end_year, group_by, mo, pl, run_query, start_year):
    _bql = f"""select * where account ~ 'Expenses' and year >= {start_year} and year <= {end_year}"""

    match group_by.value:
        case 'Year': _every = '1y'
        case 'Quarter': _every= '1q'
        case 'Month': _every = '1mo'
        case 'Week': _every = '1w'

    _df = run_query(_bql).group_by_dynamic('date', every=_every).agg(pl.col('position (USD)').sum())
    mo.ui.altair_chart(alt.Chart(_df).mark_bar().encode(x='date', y='position (USD)').properties(title=f'Expenses by {group_by.value}'))
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    /// Admonition | This is also controlled by the year slider above.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # P&L Explainer

    See https://www.gainstrack.com/pnlexplain as example of what we're trying to do here
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    We need to build

    - opening networth for each period (beginning of month) and show % change from previous period
    - also show average and total

    Below is a detailed view of the change in net worth
    """)
    return


@app.cell(hide_code=True)
def _(mo, options):
    currency = mo.ui.dropdown(options['operating_currency'], value=options['operating_currency'][0], label='Currency for report: ')
    currency
    return (currency,)


@app.cell(hide_code=True)
def _(currency, datetime, dateutil, end_year, pl, run_query, start_year):
    # This is extraordinarily slow. Need to make it faster. Almost 6 seconds just for ~7 years of data.

    _currency = currency.value

    _start = datetime.datetime(start_year, 1, 1)
    _end = datetime.datetime(end_year, 12, 31)
    _nws = []
    for dt in dateutil.rrule.rrule(dtstart=_start, freq=dateutil.rrule.MONTHLY, until=_end):
        _date_iso = dt.date().isoformat()
        _q = f"""
            SELECT convert(SUM(position),'{_currency}',{_date_iso}) as amount
            where date <= {_date_iso} AND account ~ 'Assets|Liabilities'
        """
        _df = run_query(_q)
        _nws.append((_date_iso, _df['amount (USD)'].item()))

    nw_df = pl.DataFrame(data=_nws,
                         schema=['date', 'amount'],
                         orient='row').with_columns(pl.col('amount').pct_change().alias('percent_change'))
    return (nw_df,)


@app.cell(hide_code=True)
def _(alt, mo, nw_df):
    _start = nw_df[0]['date'].item()
    _end = nw_df[-1]['date'].item()

    _amt = alt.Chart(nw_df).mark_bar(opacity=0.3, color='#57A44C').encode(x='date', y='amount')
    _pct = alt.Chart(nw_df).mark_line().encode(x='date', y='percent_change')

    mo.ui.altair_chart(alt.layer(_amt, _pct).resolve_scale(y='independent').properties(title=f'Net Worth: {_start} - {_end}'))
    return


@app.cell(hide_code=True)
def _(nw_df):
    _n = nw_df #.transpose(include_header=True)
    _n.style.tab_header(title='P&L', subtitle='with monthly change')
    _n.style.fmt_percent("percent_change").fmt_currency("amount").tab_header('Net Worth')
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
def _(Path, beancount_file, load_file, load_string, printer):
    # loading the beancount file 

    REPO = "hoostus/marimobean"
    BRANCH = "main"

    def check_if_runs_in_molab() -> bool:
        """
        Heuristic to determine if we're running in the molab environment. 
        We want to do this because in the molab environment, the beancount file is not available, 
        and we will need to download it from github.
        """

        EXPECTED_IN_MOLAB_NAMES: set[str] = {
            "__marimo__",
            "lock.txt",
            "notebook.py",
            "pyproject.toml",
        } 

        cwd = Path.cwd()
        # List the names of the files and folders in the current directory
        found_names: set[str] = {p.name for p in cwd.iterdir()}

        return EXPECTED_IN_MOLAB_NAMES.issubset(found_names)


    def fetch_github_text(path_in_repo, repo=REPO, branch=BRANCH) -> str:
        """ Fetches the text content of a file in a github repo. """
        url = f"https://raw.githubusercontent.com/{repo}/{branch}/{path_in_repo}"
        r = requests.get(url)
        r.raise_for_status()
        return r.text

    check_if_runs_in_molab: bool = check_if_runs_in_molab()

    if check_if_runs_in_molab:
        import requests
        beancount_file_string = fetch_github_text(beancount_file)
        entries, _errors, options = load_string(beancount_file_string)
    else:
        entries, _errors, options = load_file(beancount_file)

    printer.print_errors(_errors)
    return entries, options


@app.cell(hide_code=True)
def _():
    import marimo as mo
    import altair as alt
    import polars as pl

    from beancount.loader import load_file, load_string
    from beancount.parser import printer
    from beanquery.query import run_query as run_bql_query

    import datetime
    import dateutil.rrule
    from pathlib import Path

    home_dir = Path.home()
    return (
        Path,
        alt,
        datetime,
        dateutil,
        load_file,
        load_string,
        mo,
        pl,
        printer,
        run_bql_query,
    )


if __name__ == "__main__":
    app.run()
