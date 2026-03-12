import marimo

__generated_with = "0.20.4"
app = marimo.App(width="medium")


@app.cell
def _(home_dir):
    beancount_file = f'{home_dir}/Documents/beancount/my.bean'
    return (beancount_file,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    /// attention | The Australian tax year runs from July 1 to June 30.
    """)
    return


@app.cell(hide_code=True)
def _():
    TAX_YEAR_START = '2025-07-01'
    TAX_YEAR_END = '2026-06-30'
    return TAX_YEAR_END, TAX_YEAR_START


@app.cell
def _(TAX_YEAR_END, TAX_YEAR_START, beanquery2df, entries, options):
    _query = f"""select date,account,other_accounts,position
        where account ~ 'Income:Salary'
        and 'Assets:AUS:NAB:Joint0909' in other_accounts
        and date >= {TAX_YEAR_START} and date <= {TAX_YEAR_END}
        order by account;"""
    _res = beanquery2df(entries, options, _query)
    _res
    return


@app.cell(hide_code=True)
def _(beancount_file, load_file, printer):
    entries, _errors, options = load_file(beancount_file)
    # Making sure, that there are no errors in the file
    printer.print_errors(_errors)
    return entries, options


@app.cell(hide_code=True)
def _():
    import marimo as mo
    from beancount.loader import load_file
    from beancount.parser import printer
    from beanquery.query import run_query
    import pandas as pd
    from pathlib import Path
    from evbeantools.juptools import beanquery2df
    pd.options.display.float_format = "{:,.2f}".format

    home_dir = Path.home()
    return beanquery2df, home_dir, load_file, mo, printer


if __name__ == "__main__":
    app.run()
