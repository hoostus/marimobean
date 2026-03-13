import marimo

__generated_with = "0.20.4"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    /// Attention | Edit to point to your beancount file.
    """)
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
        start=_df[1]['year'].item(),
        stop=_df[-1]['year'].item(),
        full_width=True)
    return (year_slider,)


@app.cell(hide_code=True)
def _(mo, year_slider):
    mo.vstack([mo.md(f"Years selected to query: {year_slider.value[0]} - {year_slider.value[1]}"), year_slider])
    return


@app.cell(hide_code=True)
def _(run_query, year_slider):
    _start = year_slider.value[0]
    _end = year_slider.value[1]
    _bql = f"""select * where account ~ 'Income' and year >= {_start} and year <= {_end}"""
    run_query(_bql)
    return


@app.cell(hide_code=True)
def _(entries, options, pl, run_bql_query):
    def run_query(query):
        """ Convert a beancount BQL query result to a polars dataframe """
        cols, rows = run_bql_query(entries, options, query, numberify=True)
        schema = [k.name for k in cols]
        df = pl.DataFrame(schema=schema, data=rows, orient='row')
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

    from beancount.loader import load_file
    from beancount.parser import printer
    from beanquery.query import run_query as run_bql_query

    import datetime
    from pathlib import Path

    import panel as pn
    pn.extension()

    home_dir = Path.home()
    return load_file, mo, pl, printer, run_bql_query


if __name__ == "__main__":
    app.run()
