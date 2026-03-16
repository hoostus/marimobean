import marimo

__generated_with = "0.20.4"
app = marimo.App(width="medium")

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

    import datetime
    from pathlib import Path

    home_dir = Path.home()
    return (
        datetime,
        home_dir,
        load_file,
        mo,
        pl,
        pn,
        printer,
        run_bql_query,
    )

@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""/// Attention | Edit this to point to your beancount file if you want to try on real data.""") if mo.app_meta().mode == 'edit' else None
    return


@app.cell
def _(home_dir):
    #beancount_file = f'{home_dir}/Documents/beancount/my.bean'
    beancount_file = 'huge-example.beancount'
    return (beancount_file,)

if __name__ == "__main__":
    app.run()

