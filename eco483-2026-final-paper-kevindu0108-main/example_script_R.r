# Load required libraries
library(here)
library(yaml)

# Construct the path to the CSV file, relative to the root of the Git repository
csv_path <- here("data", "raw", "auto.csv")

# Load the data
auto_data <- read.csv(csv_path)

# List the first 3 observations
head(auto_data, 3)

# Calculate descriptive statistics like the mean
average_mpg <- mean(auto_data$mpg)
cat("Average MPG:", average_mpg, "\n")

# Run an OLS regression
ols_model <- lm(price ~ mpg + foreign, data = auto_data)
print(summary(ols_model))

slope_mpg <- coef(ols_model)["mpg"]
se_mpg <- summary(ols_model)$coefficients["mpg", "Std. Error"]
cat("Coefficient and Standard Error for mpg: ", slope_mpg, " (", se_mpg, ")","\n")

slope_foreign <- coef(ols_model)["foreignForeign"]
se_foreign <- summary(ols_model)$coefficients["foreignForeign", "Std. Error"]
cat("Coefficient and Standard Error for foreign: ", slope_foreign, " (", se_foreign, ")","\n")

slope_intercept <- coef(ols_model)["(Intercept)"]
se_intercept <- summary(ols_model)$coefficients["(Intercept)", "Std. Error"]
cat("Coefficient and Standard Error for intercept: ", slope_intercept, " (", se_intercept, ")\n")

# Write to results/example.yaml
result_list <- list(average_mpg = average_mpg, ols_slope_mpg = slope_mpg)
results_path <- here("results", "example.yaml")
write_yaml(result_list, results_path)
print("Results written to results/example.yaml")
