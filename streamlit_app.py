from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st


PROJECT_ROOT = Path(__file__).parent
INPUT_DIR = PROJECT_ROOT / "input_files"


st.set_page_config(
    page_title="EVE Reverse Engineering Model",
    page_icon="📊",
    layout="wide",
)


@st.cache_data
def read_input_csv(filename):
    df = pd.read_csv(INPUT_DIR / filename, skipinitialspace=True)
    df.columns = df.columns.str.strip()
    for column in df.select_dtypes(include=["object", "string"]).columns:
        df[column] = df[column].astype("string").str.strip()
    return df


@st.cache_data
def load_inputs():
    skills = read_input_csv("skills.csv")
    base_rates = read_input_csv("reverse_engineering_success_rates.csv")
    recipes = read_input_csv("reverse_engineering_recipes.csv")
    decryptors = read_input_csv("decryptor_success_rates.csv")
    prices = read_input_csv("item_prices.csv")

    skills["researched"] = skills["researched"].astype(bool)
    prices["date"] = pd.to_datetime(prices["date"])

    return skills, base_rates, recipes, decryptors, prices


def format_isk(value):
    if pd.isna(value) or np.isinf(value):
        return "Missing price"
    absolute_value = abs(value)
    if absolute_value >= 1_000_000_000:
        return f"{value / 1_000_000_000:,.1f}B ISK"
    if absolute_value >= 1_000_000:
        return f"{value / 1_000_000:,.1f}M ISK"
    return f"{value:,.0f} ISK"


def format_percent(value):
    if pd.isna(value):
        return ""
    return f"{value:.2%}"


def format_display_table(df):
    formatted = df.copy()
    isk_columns = [
        column for column in formatted.columns
        if any(token in column for token in ["cost", "price", "revenue", "profit"])
        or column in ["buy_price", "sell_price"]
    ]
    percent_columns = [
        column for column in formatted.columns
        if any(token in column for token in ["rate", "probability", "bonus", "multiplier"])
    ]
    for column in isk_columns:
        if pd.api.types.is_numeric_dtype(formatted[column]):
            formatted[column] = formatted[column].apply(format_isk)
    for column in percent_columns:
        if pd.api.types.is_numeric_dtype(formatted[column]):
            formatted[column] = formatted[column].apply(format_percent)
    return formatted.rename(columns=pretty_column_name)


def pretty_column_name(column_name):
    if column_name == "expected_cost_per_success":
        return "Cost of Success"
    custom_names = {
        "output_item_name": "Output Item",
        "input_item_name": "Input Item",
        "input_item_qty": "Qty",
        "unit_price": "Unit Price",
        "line_cost": "Line Cost",
        "base_success_rate": "Base Success Rate",
        "success_probability": "Success Rate",
        "total_skill_bonus": "Skill Bonus",
        "skill_multiplier": "Skill Multiplier",
        "decryptor_success_bonus": "Decryptor Bonus",
        "success_rate": "Final Success Rate",
        "materials_cost": "Materials Cost",
        "attempt_cost": "Attempt Cost",
        "total_attempt_cost": "Total Attempt Cost",
        "output_price": "Sell Price",
        "expected_revenue": "Probability Weighted Revenue",
        "expected_profit": "Profit Per Success",
        "estimated_input_price": "Estimated Input Price",
    }
    if column_name in custom_names:
        return custom_names[column_name]
    return column_name.replace("_", " ").title()


def add_estimated_prices(prices, price_spread_capture):
    prices = prices.copy()
    price_spread = prices["sell_price"] - prices["buy_price"]
    prices["estimated_input_price"] = prices["buy_price"] + price_spread_capture * price_spread
    return prices


def skill_bonus_from_levels(skills, selected_skill_levels):
    selected_rows = []
    for skill_name, skill_level in selected_skill_levels.items():
        if skill_level == 0:
            continue
        matching_rows = skills[
            (skills["skill_name"] == skill_name)
            & (skills["skill_level"] == skill_level)
        ]
        if not matching_rows.empty:
            selected_rows.append(matching_rows.iloc[0])
    selected_skills = pd.DataFrame(selected_rows)
    if selected_skills.empty:
        return 0, skills.iloc[0:0].copy()
    return selected_skills["skill_bonus_value"].sum(), selected_skills


def default_skill_levels(skills):
    researched = skills[skills["researched"]]
    best_by_skill = researched.loc[researched.groupby("skill_name")["skill_level"].idxmax()]
    return dict(zip(best_by_skill["skill_name"], best_by_skill["skill_level"]))


def relevant_price_items(recipes, output_item_name, decryptor_name=None):
    recipe_rows = recipes[recipes["output_item_name"] == output_item_name]
    input_items = recipe_rows.loc[
        recipe_rows["input_item_name"] != "Decryptor",
        "input_item_name",
    ].tolist()
    if decryptor_name is not None:
        input_items.append(decryptor_name)
    return sorted(set(input_items + [output_item_name]))


def apply_price_overrides(prices, price_overrides):
    prices = prices.copy()
    override_lookup = price_overrides.set_index("item_name")
    for item_name, override_row in override_lookup.iterrows():
        item_mask = prices["item_name"] == item_name
        prices.loc[item_mask, "buy_price"] = override_row["buy_price"]
        prices.loc[item_mask, "sell_price"] = override_row["sell_price"]
    return prices


def initialize_price_state(prices):
    for _, price_row in prices.iterrows():
        buy_key = session_key_from_name("buy_price", price_row["item_name"])
        sell_key = session_key_from_name("sell_price", price_row["item_name"])
        if buy_key not in st.session_state:
            st.session_state[buy_key] = 0 if pd.isna(price_row["buy_price"]) else int(price_row["buy_price"])
        if sell_key not in st.session_state:
            st.session_state[sell_key] = 0 if pd.isna(price_row["sell_price"]) else int(price_row["sell_price"])


def price_overrides_from_state(prices):
    override_rows = []
    for _, price_row in prices.iterrows():
        override_rows.append({
            "item_name": price_row["item_name"],
            "buy_price": st.session_state[session_key_from_name("buy_price", price_row["item_name"])],
            "sell_price": st.session_state[session_key_from_name("sell_price", price_row["item_name"])],
        })
    return pd.DataFrame(override_rows)


def session_key_from_name(prefix, name):
    return f"{prefix}_{name.replace(' ', '_').replace('-', '_')}"


def get_price(price_lookup, item_name, price_type):
    if item_name not in price_lookup.index:
        return np.nan
    return price_lookup.loc[item_name, price_type]


def decryptor_bonus(decryptors, decryptor_name):
    if decryptor_name is None:
        return 0
    return decryptors.loc[
        decryptors["item_name"] == decryptor_name,
        "success_rate",
    ].iloc[0]


def decryptor_label(decryptors, decryptor_name):
    if decryptor_name == "None":
        return "None"
    bonus = decryptor_bonus(decryptors, decryptor_name)
    return f"{decryptor_name} ({bonus:.2%})"


def success_probability(base_rates, decryptors, output_item_name, skill_bonus, decryptor_name):
    base_rate = base_rates.loc[
        base_rates["item_name"] == output_item_name,
        "base_success_rate",
    ].iloc[0]
    return float(np.clip(base_rate * (1 + skill_bonus) + decryptor_bonus(decryptors, decryptor_name), 0, 1))


def success_rate_breakdown(base_rates, decryptors, output_item_name, skill_bonus, decryptor_name):
    base_rate = base_rates.loc[
        base_rates["item_name"] == output_item_name,
        "base_success_rate",
    ].iloc[0]
    skill_multiplier = 1 + skill_bonus
    selected_decryptor_bonus = decryptor_bonus(decryptors, decryptor_name)
    success_rate = float(np.clip(base_rate * skill_multiplier + selected_decryptor_bonus, 0, 1))

    return pd.DataFrame([{
        "output_item_name": output_item_name,
        "decryptor_name": decryptor_name or "None",
        "base_success_rate": base_rate,
        "total_skill_bonus": skill_bonus,
        "skill_multiplier": skill_multiplier,
        "decryptor_success_bonus": selected_decryptor_bonus,
        "success_rate": success_rate,
    }])


def recipe_cost(recipes, price_lookup, output_item_name, input_price_type, decryptor_name=None):
    recipe_rows = recipes[recipes["output_item_name"] == output_item_name].copy()
    if decryptor_name is None:
        recipe_rows = recipe_rows[recipe_rows["input_item_name"] != "Decryptor"]
    else:
        recipe_rows["input_item_name"] = recipe_rows["input_item_name"].replace({"Decryptor": decryptor_name})
    recipe_rows["unit_price"] = recipe_rows["input_item_name"].apply(
        lambda item: get_price(price_lookup, item, input_price_type)
    )
    recipe_rows["line_cost"] = recipe_rows["input_item_qty"] * recipe_rows["unit_price"]
    return recipe_rows, recipe_rows["line_cost"].sum()


def model_item(base_rates, recipes, decryptors, price_lookup, output_item_name, skill_bonus, decryptor_name):
    recipe_rows, materials_cost = recipe_cost(
        recipes,
        price_lookup,
        output_item_name,
        input_price_type="estimated_input_price",
        decryptor_name=decryptor_name,
    )
    attempt_cost = base_rates.loc[
        base_rates["item_name"] == output_item_name,
        "attempt_cost",
    ].iloc[0]
    total_attempt_cost = materials_cost + attempt_cost
    output_price = get_price(price_lookup, output_item_name, "sell_price")
    p_success = success_probability(base_rates, decryptors, output_item_name, skill_bonus, decryptor_name)
    expected_revenue = p_success * output_price
    expected_cost_per_success = total_attempt_cost / p_success if p_success > 0 else np.inf
    expected_profit = output_price - expected_cost_per_success

    return pd.DataFrame([{
        "output_item_name": output_item_name,
        "decryptor_name": decryptor_name or "None",
        "success_probability": p_success,
        "materials_cost": materials_cost,
        "attempt_cost": attempt_cost,
        "total_attempt_cost": total_attempt_cost,
        "output_price_type": "sell_price",
        "output_price": output_price,
        "expected_revenue": expected_revenue,
        "expected_cost_per_success": expected_cost_per_success,
        "expected_profit": expected_profit,
    }]), recipe_rows


def show_metric_row(model_results):
    row = model_results.iloc[0]
    metric_cols = st.columns(5)
    metric_cols[0].metric("Success Rate", f"{row['success_probability']:.2%}")
    metric_cols[1].metric("Materials Cost", format_isk(row["materials_cost"]))
    metric_cols[2].metric("Total Attempt Cost", format_isk(row["total_attempt_cost"]))
    metric_cols[3].metric("Cost of Success", format_isk(row["expected_cost_per_success"]))
    metric_cols[4].metric(
        "Profit Per Success",
        format_isk(row["expected_profit"]),
        delta="Profitable" if row["expected_profit"] > 0 else "Unprofitable",
        delta_color="normal" if row["expected_profit"] > 0 else "inverse",
    )


def show_missing_price_warning(recipe_detail, model_results):
    missing_recipe_prices = recipe_detail[recipe_detail["unit_price"].isna()]["input_item_name"].tolist()
    output_missing = pd.isna(model_results.iloc[0]["output_price"])
    if missing_recipe_prices or output_missing:
        missing_items = missing_recipe_prices.copy()
        if output_missing:
            missing_items.append(model_results.iloc[0]["output_item_name"])
        st.warning(
            "Missing prices for: "
            + ", ".join(sorted(set(missing_items)))
            + ". Add prices in the sidebar to get accurate results."
        )


def main():
    st.title("EVE Reverse Engineering Profit Calculator")
    st.caption("Estimate reverse engineering success rates, costs, and profit per successful output.")

    skills, base_rates, recipes, decryptors, prices = load_inputs()
    initialize_price_state(prices)

    with st.sidebar:
        st.header("Model Controls")
        output_items = base_rates["item_name"].sort_values().tolist()
        selected_output_item = st.selectbox("Output item", output_items)

        decryptor_options = ["None"] + decryptors["item_name"].sort_values().tolist()
        selected_decryptor_option = st.selectbox(
            "Decryptor",
            decryptor_options,
            format_func=lambda option: decryptor_label(decryptors, option),
        )
        selected_decryptor = None if selected_decryptor_option == "None" else selected_decryptor_option

        with st.expander("Pricing Assumptions", expanded=True):
            price_spread_capture = st.slider(
                "Input price spread capture",
                min_value=0.0,
                max_value=1.0,
                value=0.20,
                step=0.05,
                format="%.2f",
            )
            st.caption("Input price = buy price + this fraction of the buy/sell spread.")

        relevant_items = relevant_price_items(recipes, selected_output_item, selected_decryptor)
        price_override_rows = prices[prices["item_name"].isin(relevant_items)][
            ["item_name", "buy_price", "sell_price"]
        ].copy()

        with st.expander("Price Overrides", expanded=False):
            st.caption("Edit prices here to test scenarios. These changes do not update the CSV.")
            for _, price_row in price_override_rows.iterrows():
                st.markdown(f"**{price_row['item_name']}**")
                price_columns = st.columns(2)
                price_columns[0].number_input(
                    "Buy Price",
                    min_value=0,
                    step=1,
                    key=session_key_from_name("buy_price", price_row["item_name"]),
                )
                price_columns[1].number_input(
                    "Sell Price",
                    min_value=0,
                    step=1,
                    key=session_key_from_name("sell_price", price_row["item_name"]),
                )
        price_overrides = price_overrides_from_state(prices)

        with st.expander("Skill Levels", expanded=False):
            defaults_by_skill = default_skill_levels(skills)
            selected_skill_levels = {}
            for skill_name in sorted(skills["skill_name"].unique()):
                selected_skill_levels[skill_name] = st.number_input(
                    skill_name,
                    min_value=0,
                    max_value=5,
                    value=int(defaults_by_skill.get(skill_name, 0)),
                    step=1,
                    key=session_key_from_name("skill_level", skill_name),
                )

    prices = apply_price_overrides(prices, price_overrides)
    prices = add_estimated_prices(prices, price_spread_capture)
    price_lookup = prices.set_index("item_name")
    skill_bonus, active_skills = skill_bonus_from_levels(skills, selected_skill_levels)
    model_results, recipe_detail = model_item(
        base_rates,
        recipes,
        decryptors,
        price_lookup,
        selected_output_item,
        skill_bonus,
        selected_decryptor,
    )
    success_breakdown = success_rate_breakdown(
        base_rates,
        decryptors,
        selected_output_item,
        skill_bonus,
        selected_decryptor,
    )
    selected_prices = prices[prices["item_name"].isin(relevant_items)].copy()

    st.subheader(selected_output_item)
    st.caption(f"Decryptor: {selected_decryptor or 'None'}")
    show_metric_row(model_results)
    show_missing_price_warning(recipe_detail, model_results)

    st.divider()

    tab_summary, tab_recipe, tab_prices, tab_skills, tab_raw = st.tabs([
        "Summary",
        "Recipe Cost Detail",
        "Prices",
        "Active Skills",
        "Raw Inputs",
    ])

    with tab_summary:
        st.subheader("Success Rate Breakdown")
        st.dataframe(format_display_table(success_breakdown), use_container_width=True, hide_index=True)
        st.subheader("Profit Breakdown")
        st.dataframe(format_display_table(model_results), use_container_width=True, hide_index=True)

    with tab_recipe:
        st.subheader(f"Recipe Cost Detail: {selected_output_item}")
        st.dataframe(format_display_table(recipe_detail), use_container_width=True, hide_index=True)

    with tab_prices:
        st.subheader("Relevant Market Prices")
        st.dataframe(
            format_display_table(selected_prices[["item_name", "buy_price", "sell_price", "estimated_input_price", "date"]]),
            use_container_width=True,
            hide_index=True,
        )

    with tab_skills:
        st.subheader("Selected Skill Levels")
        if active_skills.empty:
            st.info("No active skill bonuses selected.")
        else:
            st.dataframe(
                format_display_table(active_skills[["skill_name", "skill_level", "skill_bonus_value"]]),
                use_container_width=True,
                hide_index=True,
            )

    with tab_raw:
        st.subheader("Base Rates")
        st.dataframe(format_display_table(base_rates), use_container_width=True, hide_index=True)
        st.subheader("Recipes")
        st.dataframe(format_display_table(recipes), use_container_width=True, hide_index=True)
        st.subheader("Decryptors")
        st.dataframe(format_display_table(decryptors), use_container_width=True, hide_index=True)
        st.subheader("Skills")
        st.dataframe(format_display_table(skills), use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
