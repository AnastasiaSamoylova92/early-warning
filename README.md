# Early warning system
An end-to-end data science project that identifies products at risk of commercial decline one month in advance. It combines sales, customer, inventory, CRM, pipeline, marketing and market data to support earlier and more focused business decisions.

## BUsiness Objective
The system helps commercial teams:
- detect emerging revenue, unit and customer decline,
- classify product risk as **Low**, **Medium** or **High**,
- understand the main factors behind each risk prediction,
- prioritize sales, marketing ans inventory actions.

## Project Workflow
1. Generate realistic synthetic business data in Python
2. Store and prepare the data in SQL Server
3. Clean, validate, combine the datasets in Python
4. Create time-based, commercial, market and operational features
5. Train and evaluate machine-learning models using chronological data splits
6. Present risks, drivers andrecommended actions in Power BI.

## Key data & features
The model uses signa as sales momentum, customer development, rolling trends, stockouts, backorders, market demand, competitive pressure, CRM activity, pipeline value and campaign engangement.
To reducte data leakage, rolling features use historical information only, preprocessing is fitted on the training period and validation and test sets represent later time periods.