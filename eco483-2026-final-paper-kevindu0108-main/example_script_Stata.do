* Define a variable ${root} which points to the root folder of the repository
setroot

* Erase our YAML results file (if it exists) so the code writes it from scratch
capture erase "${root}/results/example.yaml"

* Load the data
import delim using "${root}/data/raw/auto.csv", clear

* List the first 3 observations
list in 1/3

* Calculate descriptive statistics like the mean
sum mpg, d
return list
yamlout using "${root}/results/example.yaml", key(average_mpg) value(`=r(mean)')

* Run an OLS regression
generate foreign_indicator = (foreign=="Foreign")
reg price mpg foreign_indicator
reg price mpg foreign_indicator, coeflegend
di "Coefficient and Standard Error for mpg: `=_b[mpg]' (`=_se[mpg]')"
di "Coefficient and Standard Error for foreign: `=_b[foreign_indicator]' (`=_se[foreign_indicator]')"
di "Coefficient and Standard Error for constant: `=_b[_cons]' (`=_se[_cons]')"
ereturn list
yamlout using "${root}/results/example.yaml", key(ols_slope_mpg) value(`=_b[mpg]')
