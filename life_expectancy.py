import marimo

__generated_with = "0.21.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import polars as pl

    return (pl,)


@app.cell(disabled=True, hide_code=True)
def _():
    import pandas as pd

    def calculate_life_table_pandas(ages, qx_values, radix=100000):
        # 1. Initialize DataFrame
        df = pd.DataFrame({'Age': ages, 'qx': qx_values})

        # 2. Calculate Survivors (lx) and Deaths (dx)
        lx = [radix]
        dx = []
        for i in range(len(df)):
            deaths = lx[i] * df.loc[i, 'qx']
            dx.append(deaths)
            if i < len(df) - 1:
                lx.append(lx[i] - deaths)

        df['lx'] = lx
        df['dx'] = dx

        # 3. Calculate Person-Years Lived in interval (Lx)
        # Standard assumption: deaths occur halfway through the year (0.5)
        df['Lx'] = df['lx'] - (0.5 * df['dx'])

        # 4. Calculate Total Person-Years (Tx)
        # Sum Lx from current age to the end of the table
        df['Tx'] = df['Lx'][::-1].cumsum()[::-1]

        # 5. Final Life Expectancy (ex)
        df['ex'] = df['Tx'] / df['lx']

        return df

    # Example Usage
    ages = [0, 1, 2, 3, 4]
    qx = [0.006, 0.001, 0.001, 0.002, 1.0] # 1.0 at final age ensures everyone dies

    life_table = calculate_life_table_pandas(ages, qx)
    print(life_table[['Age', 'lx', 'dx', 'Lx', 'Tx', 'ex']])
    return (life_table,)


@app.cell(hide_code=True)
def _(life_table):
    def calculate_last_survivor(lx_table, age_x, age_y):
        """
        Calculates Last Survivor Expectancy using the formula: ex + ey - exy
        """
        max_age = len(lx_table) - 1

        def get_expectancy(ages):
            # ages can be [age_x], [age_y], or [age_x, age_y] for joint
            max_t = max_age - max(ages)
            total_p = 0
            for t in range(1, max_t + 1):
                joint_p = 1.0
                for age in ages:
                    joint_p *= (lx_table[age + t] / lx_table[age])
                total_p += joint_p
            return total_p + 0.5  # Add 0.5 for mid-year death adjustment

        e_x = get_expectancy([age_x])
        e_y = get_expectancy([age_y])
        e_xy = get_expectancy([age_x, age_y])

        return e_x + e_y - e_xy

    # Example: Ages 65 and 70 with a sample lx_table
    # lx_table should be indexed by age (e.g., lx_table[65] is survivors at age 65)
    last_survivor_exp = calculate_last_survivor(life_table, 65, 70)
    print(f"Last Survivor Expectancy: {last_survivor_exp:.2f} years")
    return


@app.cell
def _(load_excel):
    load_excel('soa-lifetables/t2581.xls')
    return


@app.cell
def _(pl):
    import datetime

    def load_excel(filename):
        df = pl.read_excel(filename).slice(offset=21)
        df.columns = ['age', 'qx']
        df = df.with_columns(pl.col('age').cast(pl.Int64),
                               pl.col('qx').cast(pl.Float64))

        last_row = df[-1]
        last_age = last_row['age'].item()
        last_qx = last_row['qx'].item()

        # The tables end at age 105 or 120 (depending on the XLS)
        # When calculating joint mortality of couples with large
        # age differences this causes problems. You run out of data.
        # e.g. if the husband is 106 but the wife is 86 and the
        # G2 scale ends at 105...
        # So we just extend everything to 150 ensuring we have
        # enough data when we join tables later.
        extension = pl.DataFrame({
            'age': pl.int_range(last_age, 150, eager=True),
            'qx': pl.repeat(last_qx, 150-last_age, eager=True)
        })

        df = pl.concat([df, extension])
        df = df.with_columns(px = 1 - pl.col('qx'))
        return df

    male_anb_2012_iam = load_excel('soa-lifetables/t2581.xls')
    female_anb_2012_iam = load_excel('soa-lifetables/t2582.xls')
    projection_scale_g2_male = load_excel('soa-lifetables/t2583.xls')
    projection_scale_g2_female = load_excel('soa-lifetables/t2584.xls')

    def calculate_life_table(df):
        radix = 100_000
        df = df.with_columns(
            lx = (pl.col("px").shift(1, fill_value=1.0).cum_prod() * radix))

        df = df.with_columns(
            Lx = (pl.col("lx") + pl.col("lx").shift(-1, fill_value=0)) / 2)

        # 4. Total Person-Years Remaining (Tx)
        # Sum Lx from the bottom up (reverse cum_sum)
        df = df.with_columns(
            Tx = pl.col("Lx").reverse().cum_sum().reverse()
        )

        # 5. Remaining Life Expectancy (ex)
        df = df.with_columns(
            ex = pl.col("Tx") / pl.col("lx")
        )

        return df

    def adjust_g2_factor(base, g2):
        current_year = datetime.date.today().year
        n = current_year - 2012 # years since the table was created
        joint = base.join(g2, on='age')
        return joint.with_columns(pl.col('qx') * pl.col('px_right').pow(n).alias('exp')).select(['age', 'px', 'qx'])

    male = calculate_life_table(adjust_g2_factor(male_anb_2012_iam, projection_scale_g2_male))
    female = calculate_life_table(adjust_g2_factor(female_anb_2012_iam, projection_scale_g2_female))
    return female, load_excel, male


@app.cell
def _(pl):
    def pct(df, percentile):
        result = (df.sort("age").with_columns([
            # Calculate the cumulative product of (1 - qx) to get survival probability
            (pl.col("px").cum_prod()).alias("survival_prob")
        ])
        .with_columns([
            # Convert survival probability to cumulative death probability (CDF)
            (1 - pl.col("survival_prob")).alias("cdf_death")
        ])
        # Find the first age where 95% or more have died
        .filter(pl.col("cdf_death") >= percentile)
        .select(pl.col("age").min()))

        return result


    return


@app.cell
def _(female, male, pl):
    male_table = male
    female_table = female

    # Assume: Male is 60, Female is 55
    m_start, f_start = 60, 55

    # 1. Create a timeline (t = 0, 1, 2...)
    df = pl.DataFrame({"t": pl.int_range(0, 150 - min(m_start, f_start), eager=True)})

    # 2. Join mortality rates based on their age at year 't'
    df = (
        df.with_columns([
            (pl.col("t") + m_start).alias("age_m"),
            (pl.col("t") + f_start).alias("age_f")
        ])
        .join(male_table, left_on="age_m", right_on="age", how="left")
        .join(female_table, left_on="age_f", right_on="age", how="left")
    )

    df_result = df.with_columns(
        (1 - (pl.col("qx") * pl.col("qx_right"))).alias("px_sole_survivor")
    )

    df_cumulative = df.with_columns([
        # Yearly survival: px = 1 - qx
        (1 - pl.col("qx")).alias("px_m"),
        (1 - pl.col("qx_right")).alias("px_f")
    ]).with_columns([
        # Multi-year survival: tPx = Product of all px from year 0 to t-1
        # We use shift(1) because survival to year 't' depends on surviving previous years
        pl.col("px_m").shift(1, fill_value=1.0).cum_prod().alias("prob_male_alive"),
        pl.col("px_f").shift(1, fill_value=1.0).cum_prod().alias("prob_female_alive")
    ]).with_columns([
        # Probability BOTH are alive at time t (assuming independence)
        (pl.col("prob_male_alive") * pl.col("prob_female_alive")).alias("prob_both_alive")
    ])

    print(df_cumulative.select(["t", "prob_male_alive", "prob_female_alive", "prob_both_alive"]))
    return


if __name__ == "__main__":
    app.run()
