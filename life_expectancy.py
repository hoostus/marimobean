import polars as pl
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

def get_survival_probs(df, start_age):
    return (
        df.filter(pl.col("age") >= start_age)
        .with_columns(
            surv_prob = pl.col("px").cum_prod().shift(1, fill_value=1.0)
        )
        .select(["age", "surv_prob"])
    )

def get_percentile_life_expectancy(percentile, table_1, age_1, table_2, age_2):
    surv_1 = get_survival_probs(table_1, age_1).rename({"surv_prob": "s1", "age": "age1"})
    surv_2 = get_survival_probs(table_2, age_2).rename({"surv_prob": "s2", "age": "age2"})

    # Align by year 't' (years from now)
    joint_df = (
        surv_1.with_row_index("t")
        .join(surv_2.with_row_index("t"), on="t")
        .with_columns(
            # Probability that AT LEAST one is alive
            joint_survival = 1 - (1 - pl.col("s1")) * (1 - pl.col("s2"))
        )
    )

    # 4. Find the 90th percentile (where joint survival drops to 10%)
    return (
        joint_df.filter(pl.col("joint_survival") <= (1-percentile))
        .select(pl.col("t").min())
        .item()
    )

if __name__ == '__main__':
    print(get_percentile_life_expectancy(0.90, male, 50, female, 35))
