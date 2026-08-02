# Early warning system
An end-to-end data science project that identifies products at risk of commercial decline **one month in advance**. It combines sales, customer, inventory, CRM, pipeline, marketing and external market signals to help commercial teams intervene earlier and focus resources on the products and regions with the greatest business impact.

> **Portfolio project:** The data used in this project is synthetic and was created to represent a realistic multi-market B2B environment. It does not contain confidential company or customer information.

## Business Objective
Commercial deterioration rarely appears in a single KPI. Revenue may still look stable while unit sales, active customers, pipeline activity or market demand are already weakening. This project brings these signals together in an early-warning framework that helps teams:

- detect emerging revenue, unit and customer decline;
- classify product-region combinations as **Low**, **Medium** or **High Risk**;
- understand the commercial and market drivers behind each prediction;
- estimate the revenue currently exposed to elevated risk;
- prioritize sales, marketing, pricing and inventory actions;
- monitor model quality and data reliability in Power BI.

## Project Workflow
```text
Synthetic business data
        ↓
SQL Server storage and preparation
        ↓
Python data validation and feature engineering
        ↓
Chronological train, validation and test split
        ↓
Machine-learning model and risk classification
        ↓
Power BI early-warning and model-monitoring dashboards
```

## Data Foundation
The analytical dataset combines multiple business perspectives at product, region and monthly level.

| Data area | Example signals |
|---|---|
| Sales | Revenue, units, ASP, discounts, gross profit and gross margin |
| Customers | Active customers, new customers, customer losses and revenue retention |
| Inventory | Stock levels, stockouts, backorders and inventory pressure |
| CRM activity | Customer interactions, opportunities and recent sales activity |
| Pipeline | Pipeline value, coverage, opportunity development and conversion signals |
| Marketing | Campaign activity, engagement and marketing support |
| Market context | Market demand, competitor pressure and category-region position |
| Product | Product group, lifecycle stage, launch date and target margin |

## Feature Engineering
The model uses historical features designed to capture both gradual deterioration and sudden changes, including:

- month-over-month and rolling revenue and unit development;
- three- and six-month rolling averages;
- sales volatility and consecutive decline indicators;
- active-customer trends and customer concentration;
- gross-margin performance and deviation from target;
- category-region share and product lifecycle;
- inventory shortages, stockouts and backorder pressure;
- CRM, pipeline and campaign activity;
- market-demand and competitive-pressure indicators.

These signals allow the model to distinguish isolated monthly fluctuations from broader patterns of commercial decline.

## Modelling Approach
The project treats early-warning detection as a supervised multi-class classification problem:

- **Low Risk:** no material deterioration expected;
- **Medium Risk:** emerging warning signals require monitoring;
- **High Risk:** strong deterioration signals require prioritization.

Simple benchmarks, including a majority-class model and Gaussian Naive Bayes, were compared with the final Random Forest model. Model selection was based on a balanced view of overall performance and the operational requirement to identify high-risk cases.

### Test-set performance
| Model | Accuracy | Macro F1 | High-Risk Recall |
|---|---:|---:|---:|
| Majority Class | 53.4% | 23.2% | 0.0% |
| Gaussian Naive Bayes | 44.8% | 44.2% | 50.4% |
| Random Forest | **70.5%** | **69.1%** | **70.1%** |

The selected model uses a decision threshold of **0.58** to balance high-risk detection with the number of false alerts generated for business users.

## Leakage Prevention and Validation
Because the project predicts future commercial decline, the modelling process follows time-aware validation principles:

- the target represents risk in the **following month**;
- rolling features use historical information only;
- preprocessing is fitted on the training period;
- training, validation and test sets represent consecutive time periods;
- future observations are not used to calculate historical features;
- model performance is reported on a later, unseen test period.

This design provides a more realistic estimate of how the model would behave in a production environment.

## Risk Outputs
For each scored product-region combination, the solution produces:

- predicted risk class and probability;
- normalized risk score;
- current revenue, units and active customers;
- key risk drivers;
- commercial context and rolling baselines;
- revenue under watch;
- prioritized alert ranking.

Example drivers include sales below trend, high sales volatility, recent sales decline, customer loss, high competitive pressure and margin below target.

## Power BI Dashboard
The Power BI report converts model outputs into an operational decision-support tool. It includes executive KPIs, prioritization tables, drill-through analysis, model monitoring and data-quality controls.

### Executive Overview
Portfolio-level view of revenue, gross margin, forecast accuracy, active customers, revenue at risk and net revenue retention, together with the latest risk developments.
![Executive Overview](images/01_overview.png)

### Risk Operations
Prioritized worklist of high-risk product-region alerts, including commercial exposure, lifecycle, risk score and main drivers.
![Risk Operations](images/02_risk_operations.png)

### Product Risk Details
Drill-through analysis of an individual product-region alert, including recent commercial performance, rolling baselines, market context and local business drivers.
![Product Risk Details](images/03_product_risk_details.png)

### Model Performance
Model comparison, confusion matrix and monitoring KPIs such as accuracy, Macro F1, high-risk recall, precision, false-alarm rate and alert rate.
![Model Performance](images/04_model_performance.png)

### Data Quality
Monitoring of feature coverage, missing enrichment values, duplicate keys and the completeness of the model-scoring dataset.
![Data Quality](images/05_data_quality.png)

## Technology Stack
| Layer | Technologies |
|---|---|
| Data generation and analysis | Python, pandas, NumPy |
| Machine learning | scikit-learn |
| Database | SQL Server, SQL |
| Data modelling | Dimensional model / star schema |
| Business intelligence | Power BI, Power Query, DAX |
| Development | Jupyter Notebook, Git, GitHub |

## Key Project Strengths
- Connects machine-learning output to concrete commercial decisions.
- Combines financial, customer, operational and market data in one analytical model.
- Uses chronological validation and explicit leakage controls.
- Evaluates the model using business-relevant metrics rather than accuracy alone.
- Provides interpretable risk drivers and prioritized alerts instead of isolated predictions.
- Includes model-performance and data-quality monitoring alongside business dashboards.

## Potential Next Steps
- automate monthly scoring and dashboard refreshes;
- add alert ownership, status and intervention tracking;
- measure whether commercial actions reduce future risk;
- introduce probability calibration and threshold optimization by business cost;
- monitor feature drift and model performance over time;
- deploy the data pipeline using Microsoft Fabric or another cloud platform.

## Author
**Ana Sam**  
Business Intelligence & Data Analytics Portfolio Project

