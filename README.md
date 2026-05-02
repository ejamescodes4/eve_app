# EVE Reverse Engineering Model

A Streamlit app for modeling EVE Online reverse engineering jobs. The app reads CSV files from `input_files`, calculates reverse engineering success rates, estimates recipe costs, supports manual price overrides, and compares expected profitability for selected output items.

## Features

- Select an output item to model.
- Select a decryptor or choose no decryptor.
- Adjust buy and sell prices manually without changing the CSV files.
- Adjust skill levels from 0 to 5.
- View success rate breakdowns.
- View recipe cost details.
- View expected cost of success and expected profit.
- Display ISK values in readable formats like `14.5B ISK` and `250.0M ISK`.

## Project Structure

```text
.
├── input_files/
│   ├── decryptor_success_rates.csv
│   ├── item_prices.csv
│   ├── reverse_engineering_recipes.csv
│   ├── reverse_engineering_success_rates.csv
│   └── skills.csv
├── requirements.txt
├── streamlit_app.py
└── README.md
```

## Setup

From the repo folder, create and activate a Python virtual environment.

```powershell
python -m venv .venv
& .\.venv\Scripts\Activate.ps1
```

Install dependencies.

```powershell
python -m pip install -r requirements.txt
```

## Run the App

If you are in the repo folder:

```powershell
python -m streamlit run streamlit_app.py
```

If you are in the parent `git` folder:

```powershell
& .\.venv\Scripts\python.exe -m streamlit run .\eve_app\streamlit_app.py
```

## How to Use

1. Open the Streamlit app in your browser.
2. Choose an `Output item` from the sidebar.
3. Choose a `Decryptor`, or select `None`.
4. Adjust the `Input price spread capture` slider if needed.
5. Edit item buy/sell prices in `Price Overrides`.
6. Set skill levels from 0 to 5 in `Skill Selection`.
7. Review the top metrics:
   - Success Rate
   - Materials Cost
   - Total Attempt Cost
   - Cost of Success
   - Expected Profit
8. Use the tabs to inspect model details, recipe costs, active skills, relevant prices, and raw input data.

## Model Notes

Success rate is calculated as:

```text
base_success_rate * (1 + total_skill_bonus) + decryptor_success_bonus
```

Total attempt cost is calculated as:

```text
materials_cost + attempt_cost
```

Cost of success is calculated as:

```text
total_attempt_cost / success_probability
```

Expected profit is calculated as:

```text
output_sell_price - cost_of_success
```

Input item prices are estimated as:

```text
buy_price + input_price_spread_capture * (sell_price - buy_price)
```

Output item value uses the listed `sell_price`.

## Input Files

All source data lives in `input_files`.

- `item_prices.csv`: item names, sell prices, buy prices, and price date.
- `reverse_engineering_recipes.csv`: output items, input items, and quantities.
- `reverse_engineering_success_rates.csv`: base success rates and attempt costs.
- `decryptor_success_rates.csv`: decryptor names and success bonuses.
- `skills.csv`: skill names, levels, researched status, and bonus values.

Manual price changes in the app do not update the CSV files. They only persist while the Streamlit session is running.

## Git: Save and Push Changes

Check changed files.

```powershell
git status
```

Add the app files.

```powershell
git add README.md requirements.txt streamlit_app.py input_files
```

Commit the changes.

```powershell
git commit -m "Add Streamlit reverse engineering model"
```

Push to GitHub.

```powershell
git push
```

If this is the first push for the branch, use:

```powershell
git push -u origin main
```

If your branch is named something else, check it with:

```powershell
git branch --show-current
```

Then push that branch:

```powershell
git push -u origin your-branch-name
```
