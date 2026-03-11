# Load required libraries
import pandas as pd
from pyhere import here
import statsmodels.api as sm
import yaml

# Construct the path to the CSV file, relative to the root of the Git repository
csv_path = here("data", "raw", "auto.csv")

# Load the data
auto_data = pd.read_csv(csv_path)

# List the first 3 observations
print(auto_data.head(3))

# Calculate descriptive statistics like the mean
average_mpg = auto_data['mpg'].mean()
print(f"Average MPG: {average_mpg}")

# Run an OLS regression
auto_data['foreign'] = auto_data['foreign'].apply(lambda x: 1 if x == 'Foreign' else 0)
auto_data = sm.add_constant(auto_data)
ols_model = sm.OLS(auto_data['price'], auto_data[['const', 'mpg', 'foreign']]).fit()

print(ols_model.summary())

slope_mpg = ols_model.params['mpg']
se_mpg = ols_model.bse['mpg']
print(f"Coefficient and Standard Error for mpg: {slope_mpg} ({se_mpg})")

slope_foreign = ols_model.params['foreign']
se_foreign = ols_model.bse['foreign']
print(f"Coefficient and Standard Error for foreign: {slope_foreign} ({se_foreign})")

slope_intercept = ols_model.params['const']
se_intercept = ols_model.bse['const']
print(f"Coefficient and Standard Error for intercept: {slope_intercept} ({se_intercept})")

# Write to results/example.yaml
result_list = {
    "average_mpg": float(average_mpg),
    "ols_slope_mpg": float(slope_mpg),
}
results_path = here("results", "example.yaml")
with open(results_path, "w") as yaml_file:
    yaml.dump(result_list, yaml_file)
print("Results written to results/example.yaml")
