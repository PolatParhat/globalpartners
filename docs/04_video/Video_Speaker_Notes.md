# Video script: GlobalPartners Business Insights Pipeline

Read this top to bottom while you share your screen. About 13 minutes at a calm pace.
**SCREEN:** lines tell you what to have open. Everything else is spoken text, word for word.
Meter is running at about $0.42 an hour, so do the setup below first, record in one go, then run `infra/down.sh`.

**Setup (2 minutes, before recording):** open six browser tabs in this order: 1) the architecture diagram `docs/03_architecture/global-partner-pipeline-architecture.png`,
2) Airflow (AWS console, MWAA, Open Airflow UI, DAG `globalpartners_daily`), 3) the dashboard link from `up.sh`, 4) AWS console, CloudFormation, `GlobalPartnersPipeline`, Resources, 5) `config/business_rules.yaml`, 6) GitHub: the Actions tab and the pull requests list.
Zoom the browser to 125 %. Hide the account number, your email and your IP. Close Slack and mail.

---

## 1. Introduction

**SCREEN:** tab 1, the architecture diagram.

Hello, and thank you for watching. My name is Polat, and this is my demonstration of the GlobalPartners Business Insights Pipeline.

GlobalPartners runs restaurants under the Alltown Fresh brand. Every order is stored in a SQL Server database. Management wants one trustworthy view of customer behavior, spending, and business performance.

The main number they asked for is Customer Lifetime Value, or CLV, and they want it recalculated every single day. In this project, CLV means the total amount a customer has spent so far.

I built the full pipeline, from the SQL Server database to a live dashboard, on AWS, using only the tools in the requirements document: SQL Server, PySpark on AWS Glue, Apache Iceberg on S3, Airflow, Streamlit, AWS CDK, and GitHub Actions.

The scope is orders from 2023, as you confirmed.

## 2. The data and the rules

**SCREEN:** tab 5, `config/business_rules.yaml` (open it on GitHub or in your editor). Scroll slowly as you name each rule.

Before building anything, I analyzed the source files and wrote down every decision. You approved the design on the 14th of October.

For 2023, the numbers are: 52,015 orders, 746 thousand dollars in revenue, 20 restaurant locations, and 10,512 customers.

A few rules shape every number, and they all live in one configuration file, so changing a rule means changing a setting, not rewriting code.

First, one of the apps is test data, so those orders are loaded but excluded from every metric. Second, guest orders, the ones without a customer, count in sales but not in customer metrics, as you confirmed. Third, one faulty account is not a real customer, so I exclude it from customer metrics but keep its revenue in sales. Fourth, a line's revenue is the item price plus each option's price times the quantity. Fifth, the business day follows New York time. Sixth, a customer is active up to 45 days since their last order, at risk between 46 and 90 days, and lapsed after 90 days.

Three of these are still assumptions that I need you to confirm: the option price per unit, the New York time zone, and whether the faulty account's sales are real. Each one is written down with its impact, and each is a single setting to change.

Also, as you told me, the data has no discounts and no location names, only a restaurant id. The dashboard says so openly instead of inventing anything.

## 3. Architecture

**SCREEN:** still the diagram. Point at each box as you name it, left to right.

The data flows through layers, like a factory line.

It starts at the source, SQL Server on Amazon RDS. This is the cash register of the restaurants.

Next is bronze. Bronze is an exact copy of what the source sent, with a batch id and a load time. Nothing is changed, only appended.

Then silver. Silver is the cleaned version: correct types, trimmed text, and flags for guests and test data. Rows that cannot be used are not dropped silently. They go to a quarantine table together with the reason.

Then gold. Gold is the finished product: a star schema with fact tables and dimension tables, plus the metric tables the dashboard reads.

And beside all of them is an ops area, the logbook of the factory. It stores where each load stopped, a record of every run, and the result of every quality check.

This pattern is called the medallion architecture. Its big advantage is that if a business rule changes, I can rebuild silver and gold from bronze without ever touching the source.

The processing is PySpark running on AWS Glue, which is serverless Spark, so there is no cluster to manage. The tables are Apache Iceberg tables on S3. Iceberg gives plain files database powers: safe merge writes and the ability to go back to an earlier version of a table.

Airflow, running on Amazon MWAA, schedules the work. Athena runs SQL on the gold tables. The dashboard runs on ECS Fargate behind a load balancer. Encryption, the database password, and permissions are handled by KMS, Secrets Manager, and IAM roles with least privilege.

And all of this infrastructure is code, written with the AWS CDK.

## 4. The daily pipeline

**SCREEN:** switch to tab 2, Airflow. Open the DAG `globalpartners_daily`, Graph view.

This is the daily pipeline in Airflow. Every morning at 6 AM it starts one run, and each run has six steps.

Step one, replay day. The source files are a static snapshot, so this step simulates the restaurants by copying one business day of orders into the live SQL Server tables.

Step two, extract to bronze. It copies the orders that are new or changed since the last successful load, plus a three day safety window for late rows.

Step three, bronze to silver. It cleans the data, flags rows, and quarantines anything unusable.

Step four, silver to gold. It builds the facts and the dimensions.

Step five, gold metrics. It rebuilds the daily CLV snapshot and the sales and location tables.

Step six, data quality checks. There are 25 checks, and if any one fails, the run fails and the dashboard keeps the last good data.

This is also how failures are handled. The pipeline keeps a bookmark of the newest order it has loaded, and the bookmark only moves forward after a successful run. So if a run fails, the next run automatically reads the missed data again, and because the writes are merges, reading it again never creates duplicates. Airflow also retries a failed task twice before giving up.

**SCREEN:** click a green run, open the log of the `replay_day` task.

Here is a task log. You can see the job report how many orders, lines, and options it added for that day.

## 5. How I loaded the full year

**SCREEN:** the Runs list of the DAG in Airflow.

A real business adds one day at a time, but for this demo I needed the whole year. So I ran this same pipeline several times.

The first three runs were single days, to prove the daily behavior: the 1st, 2nd, and 3rd of January, with 63, 96, and 130 orders.

Then I added one optional run setting, called replay_until. It lets one run replay a range of days, and then run the same six steps once over everything it received. If you leave it empty, a run does one day, exactly as before.

With that setting I loaded the rest of January, then February to May, then June to December, in three more runs. Altogether the system holds 52,641 orders. 52,015 of them count in the metrics, because 626 orders belong to the test app and are excluded.

**SCREEN:** tab 4, the CloudFormation resources list.

Everything you see on AWS was created from code by one command: the network, the database, the Glue jobs, Airflow, the dashboard service, and the load balancer.

## 6. Proof that the result is correct

**SCREEN:** tab 3, the dashboard. Point at the totals on the first page and on Sales trends as you say each figure. Say this slowly.

I did not just trust the load. I counted the result in Athena and compared it with a reference I calculated directly from the raw files.

Orders: 52,015 on AWS, 52,015 in the reference. Revenue: 746,223 dollars and 86 cents on both. Customers: 10,512 on both. Total CLV at the end of the year: 673,614 dollars and 4 cents on both. Daily snapshot rows: 2,283,740 on both. Locations: 20 on both.

Same code, same numbers, to the cent, locally and on AWS. And all 25 quality checks pass on the final run.

## 7. The dashboard

**SCREEN:** tab 3, the dashboard. Click each page in the left menu as you talk.

The dashboard has six pages, one for each business question. It reads the gold tables through Athena, and it cannot change any data, because its AWS role is read-only.

In the sidebar there is an "as of" date. It decides which day the customer pages describe. It is set to the 31st of December, and I can move it to an earlier date to show how the customer view changes over time.

**Customer segmentation.** This answers who our customers are. Each customer gets a score from one to five for recency, frequency, and monetary value, which is called RFM. Customers who score high on everything are VIPs. Customers with low recency and low frequency are in Churn Risk. New customers ordered recently and for the first time within 90 days. The page also shows the CLV tiers, where High is the top 20 percent and Low is the bottom 20 percent.

I used fixed score bands instead of equal-sized groups, because more than 80 percent of customers have zero or one order in any 90 day window, and fixed bands mean a score has the same meaning every day.

**Churn risk.** This answers who is leaving. Here are the three churn groups, active, at risk, and lapsed. *(Read the three counts and labels from the screen.)* There is a threshold slider, and below it a re-engagement list of the customers the business should contact.

**Sales trends.** This answers when we sell. It shows revenue over time with holidays, when customers order by weekday and hour, and revenue by product category.

**Loyalty program.** This answers whether loyalty pays off. Members have a higher average CLV and come back more often than non-members. I want to be careful here: this shows an association, not proof that the program causes it.

**Location performance.** This answers which restaurants lead. It ranks locations by revenue. They are shown by id, because the source has no location names.

**Pricing and discounts.** This page states the limitation you confirmed: the data contains no discounts, so there is nothing to analyze, and I preferred to say that clearly.

## 8. The data model and daily CLV

**SCREEN:** open `docs/03_architecture/global-partner-data-model.png`, or stay on the dashboard.

The model is a star schema. In the center are two fact tables: one row per order line, and one row per order. I keep both so that an order is never counted once per item.

Around them are the dimensions: customer, location, item, app, and date.

The most important table is the customer daily snapshot. It has one row for every customer for every day, from their first order to the last loaded day, including days with no orders, because recency and churn status keep changing on those days. For 2023 it has 2,283,740 rows.

Here is a real example from the design. A customer orders on the 8th of May for 12 dollars and 99 cents, and is New and active. On the 25th of June they have not ordered, so they are Churn Risk and at risk. On the 26th of June they order again, spend 34 dollars and 97 cents in total, and become a VIP. By the end of the year, with no further orders, they are back to Churn Risk. This evolution of a customer's value over time is what the pipeline exists to produce.

One more point: the loyalty card number stays in silver and never reaches gold or the dashboard.

## 9. Quality and failure handling

**SCREEN:** tab 2, Airflow. Open the latest run and the log of the `dq_checks` task, where the checks are listed.

A bad number should fail loudly, not appear quietly on a dashboard. So the pipeline has several protections.

Unusable rows go to quarantine with their reasons. The 25 quality checks confirm that row counts reconcile between layers, that revenue is identical in orders, order lines, and every aggregate, that keys are unique, and that every fact finds its dimensions.

If a Glue job fails, an alert is published to an email notification topic. Writes are safe to repeat. Iceberg keeps earlier table versions, so a bad load can be reversed. And every row carries a batch id, so I can trace any number back to the run that produced it.

I saw this working for real. When I first switched the pipeline on, Airflow started a run for today's date. My data only covers 2023, so that run loaded zero orders, and the quality step failed the run instead of publishing an empty result. That is the safety net doing its job.

## 10. What the first real deployment taught me

**SCREEN:** tab 6, the GitHub repository's Actions tab (green runs) and the pull requests list.

The whole pipeline was first built and tested on my laptop with Docker images of the same components AWS runs. There are 99 unit tests and 21 infrastructure tests, and they run in GitHub Actions on every change. Every change goes through a branch and a pull request.

Still, deploying to the real cloud for the first time found problems that local tests could not. I want to be honest about them.

First, Airflow refused to be created, because I had switched two log types off without giving them a log level, and AWS requires a level even for a log that is switched off. I fixed it and added a test.

Second, the dashboard crashed with "no module named dashboard", because of how Streamlit sets Python's search path. I fixed it in the container image and tested it inside the real image.

Third, loading the whole year in one step hung, because it created one huge database transaction on the smallest database size. I solved it by loading the year in chunks through the same pipeline, which is why the replay_until setting exists.

And fourth, I mistyped a date, the 31st of April, which does not exist. The job rejected it immediately, and it failed fast and cheap.

Each of these was fixed on its own branch, with a test. That is the value of deploying early and of making every failure loud.

On cost: the always-on parts cost about 42 cents an hour. The whole demo day, including the failed attempts, cost roughly 9 dollars. I will delete everything right after this recording.

## 11. Limitations and next steps

I want to name the limitations before you ask.

The dashboard uses HTTP, limited to one IP address, not HTTPS, because HTTPS needs a domain name and certificate, and this project has none. This differs from the approved design, and I recorded it. Production would use a domain, a certificate, and company sign-in.

The database is single-zone and the smallest size, with no backups, because this is a short demo. Production would use multi-AZ, backups, and point-in-time recovery.

The restaurants are simulated by the replay job. In production we would connect the real point-of-sale database.

Deleted orders in the source are not detected, because the incremental load only sees new and changed rows. Production would use SQL Server change data capture.

And there are the open assumptions I mentioned: option price per unit, the New York business day, the faulty account, the zero-dollar menu item, and the three day change window. Each one is a single setting.

## 12. Closing

**SCREEN:** back to the dashboard, on the first page.

In summary: a complete pipeline from SQL Server to a dashboard, with daily CLV, 25 automated quality checks, tested code, and infrastructure I can create or delete with one command.

It ran on AWS for the whole of 2023 and matches the reference numbers to the cent. The open questions for you are the assumptions in the design document.

Thank you for watching.
