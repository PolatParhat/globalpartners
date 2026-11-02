# Video speaker notes: GlobalPartners Business Insights Pipeline

Audience: the SME. Target length: **12 to 15 minutes**. Record in one take per section; you can cut between sections.
These notes are written in plain words on purpose: read them once end to end and you understand the whole project.
Lines in **bold quotes** are what to say (in your own words); the rest is background for you.

---

## 0. Before you press record

**Cost reminder:** everything on AWS costs about **$0.42 per hour** while it exists. Prepare first, record fast, then run `infra/down.sh`.

| Check | How |
|---|---|
| Dashboard opens on your recording browser | the link printed by `up.sh` (HTTP, not HTTPS); only your IP can open it |
| Airflow UI open | AWS console → MWAA → globalpartners → Open Airflow UI |
| The DAG shows 3 green runs (1, 2, 3 January 2023) | Airflow → `globalpartners_daily` → Runs |
| Four browser tabs ready, in this order | 1 architecture diagram (`docs/03_architecture/global-partner-pipeline-architecture.png`), 2 Airflow, 3 dashboard, 4 AWS console (CloudFormation → GlobalPartnersPipeline → Resources) |
| Hide private things | do not show the account number, your IP address or your email. Crop or blur the top-right of the AWS console |
| Zoom the browser to 125 % | readable on a recording |
| Close notifications | Slack, mail, calendar |

**One honest warning to keep in mind while speaking:** the AWS demo has only **3 days of data** (1 to 3 January 2023), so charts are small.
The **full-year figures** (52,015 orders, 10,512 customers, and so on) come from the local run on the whole of 2023.
Always say which of the two you are quoting.

---

## 1. Opening: the problem and the goal (about 1 minute)

**Say:** "GlobalPartners runs restaurants (Alltown Fresh). Their orders sit in a SQL Server database. Management wants one trustworthy view of
customer behaviour, spend and business performance. The main number is **Customer Lifetime Value, CLV, recalculated every day**.
I built the pipeline that produces it, from the database to a dashboard, on AWS, using only the tools in the requirements."

Background:
- **CLV** here means *historical spend to date* per customer (no prediction). The requirements document defines it as total spend per customer.
- **"Recalculated every day"** is the hard part: we keep a row for every customer for every day, so we can show how a customer's value and status
  *evolve* (for example, a VIP drifting into "Churn Risk").
- **Scope:** 2023 orders only (the SME confirmed).
- **Tools (all from the requirements):** SQL Server (RDS), PySpark on AWS Glue, Apache Iceberg on S3, Airflow on MWAA, Streamlit, AWS CDK, GitHub Actions.
  No Snowflake, dbt, Terraform or other external tools.

---

## 2. The data and what I decided (about 1.5 minutes)

**Say:** "Before building, I verified and analysed the source files, and I wrote down every decision. The SME approved the design on 14 October 2026."

The numbers (2023, in scope): **52,015 orders, $746,223.86 revenue, 20 locations, 10,512 customers.**

Rules that shape every number (all live in one file, `config/business_rules.yaml`, so an SME answer changes a setting, not the code):

| Rule | In plain words |
|---|---|
| Test data excluded | the app `Alltown Fresh - DEVELOPMENT` is test traffic (SME confirmed) |
| Guests | orders without a customer id count in **sales**, not in **customer** metrics (SME confirmed) |
| One faulty account | account `5ece77fe…` (937 orders) is not a real customer; excluded from customer metrics, its revenue stays in sales (assumption Q11a) |
| Revenue per line | `item_price` (already the line total) + each option's price × quantity (assumption Q3) |
| Business day | order time converted from UTC to New York time (assumption Q10) |
| Churn status | active up to 45 days since the last order, at risk 46 to 90, lapsed over 90 (SME confirmed) |

**Say, about assumptions:** "Three things the SME has not confirmed (option price per unit, New York time zone, whether the faulty account's sales are real)
are written down, each with its impact if wrong, and each is one setting to change."

**Two data limitations the SME told me to mention:** the data has **no discounts** and **no location names** (only `restaurant_id`).
The dashboard states both openly instead of inventing anything.

---

## 3. Architecture: the big picture (about 2 minutes)

Show tab 1 (architecture diagram). Walk left to right.

**Say:** "Data flows through four layers, like a factory line: raw material, cleaned parts, finished products, and the shop window."

| Layer | Analogy | What it holds | How it is written |
|---|---|---|---|
| **Source** (SQL Server on RDS) | the shops' cash registers | `order_items`, `order_item_options`, `date_dim` | a replay job simulates each day's orders |
| **Bronze** | goods delivery, unopened | exact copy of what the source sent, plus batch id and load time | append only |
| **Silver** | cleaned and labelled | typed, trimmed, flagged (guest, test data); broken rows go to `quarantine` with a reason | MERGE (insert new, update changed) |
| **Gold** | finished products on the shelf | star schema (facts and dimensions) and metric tables | MERGE or rebuilt |
| **Ops** | the factory's logbook | `watermarks` (where we stopped), `pipeline_runs` (every run), `dq_results` (check results) | written by every run |

This pattern is called the **medallion architecture** (bronze, silver, gold). Why it is good: if a business rule changes, I rebuild silver or gold
from bronze and never touch the source.

Components in one line each:
- **Amazon RDS for SQL Server Express:** the source database (managed by AWS, license included).
- **AWS Glue 5.1 (PySpark):** serverless Spark. No cluster to manage. **Eight Glue jobs**: `setup_source`, `load_seed`, `replay_day` (set-up and simulation) and five pipeline jobs
  (`extract_to_bronze`, `bronze_to_silver`, `silver_to_gold`, `gold_metrics`, `dq_checks`).
- **Amazon S3 + Apache Iceberg:** the data lake. Iceberg is a table format that gives files database powers: reliable writes (MERGE), and **time travel** (go back to an earlier version of a table).
- **Glue Data Catalog:** the address book that tells Glue and Athena where each table lives.
- **Amazon MWAA (Airflow):** the scheduler. Runs the six steps in order every day at 06:00 and retries failures.
- **Amazon Athena:** runs SQL directly on the gold tables. The dashboard uses it.
- **ECS Fargate + Application Load Balancer:** runs the Streamlit dashboard without a server to manage.
- **KMS key + Secrets Manager + IAM roles:** encryption, the database password, and least-privilege permissions.
- **AWS CDK + GitHub Actions:** the whole infrastructure is code, and every change is tested automatically.

---

## 4. One day of the pipeline, then the live demo (about 3 minutes)

**Say, in plain words:** "Every morning at 06:00 Airflow starts one run. A run is six steps."

| # | Task | What it does in one sentence |
|---|---|---|
| 1 | `replay_day` | simulates the shops: copies that business day's orders into the live SQL Server tables (the source files are a static snapshot, so this is how daily arrival is shown) |
| 2 | `extract_to_bronze` | copies new and changed orders since the last successful load (minus a 3-day safety window for late rows) into bronze |
| 3 | `bronze_to_silver` | cleans, types and flags rows; sends unusable rows to quarantine |
| 4 | `silver_to_gold` | builds the facts (order and order-line level) and the dimensions |
| 5 | `gold_metrics` | rebuilds the daily CLV snapshot and the sales and location tables |
| 6 | `dq_checks` | 25 data-quality checks; if one fails, the run fails and the dashboard keeps the last good data |

**Why "watermark + 3 days":** the watermark remembers the newest order we loaded. It only moves forward after a **successful** run, so a failed run is
automatically re-read next time. MERGE writes mean re-reading never creates duplicates. That is the **failure reload mechanism** the requirements ask for.

### Live demo steps (tab 4, then tab 2)

1. **AWS console, CloudFormation:** "Everything you see here was created from code by one command." Show the resource list (VPC, RDS, Glue jobs, MWAA, ECS service, load balancer).
2. **Airflow, Graph view of `globalpartners_daily`:** show the six tasks and three green runs. Click one run, open a task log (for example `replay_day`).
3. **Read the numbers from the logs** (these are exact and match the local reference):

| Day | Orders | Lines | Options |
|---|---|---|---|
| 1 Jan 2023 | 63 | 120 | 105 |
| 2 Jan 2023 | 96 | 159 | 173 |
| 3 Jan 2023 | 130 | 184 | 151 |

   **Say:** "The same three days give exactly the same numbers locally and on AWS. That is the proof that the code behaves the same in both places."

4. **The red run (optional but a strong story):** Airflow may also show a red run dated **today (2 November 2026)**. Explain it:
   "When I switched the DAG on, Airflow started a run for today. The data only covers 2023, so there were no orders, and the data-quality step **correctly failed the run**.
   An empty load is exactly what that safety check exists to catch." Then: "In production this would send an alert email through SNS."
   (If you do not see it, skip it.)

---

## 5. The dashboard (about 3 minutes)

Show tab 3. Six pages, one per business question in the requirements. In the AWS demo only 3 days exist, so use the **sidebar "as of" date** to show
the numbers moving between 1, 2 and 3 January.

**Say first:** "The dashboard reads the gold tables through Athena. It cannot change anything: its AWS role is read-only."

| Page | The question | What to point at |
|---|---|---|
| **Customer segmentation** | who are our customers? | RFM segments (VIP, New, Regular, Churn Risk), the recency × frequency grid, CLV tiers (High = top 20 %, Low = bottom 20 %), segments over time |
| **Churn risk** | who is leaving? | churn status counts, the threshold slider, the **re-engagement alert** list of customers to contact |
| **Sales trends** | when do we sell? | revenue over time, holidays, when customers order (weekday and hour), revenue by product category |
| **Loyalty program** | does loyalty pay off? | members vs non-members: average CLV, repeat-order rate |
| **Location performance** | which restaurants lead? | revenue ranking, what distinguishes top performers, full table (by `restaurant_id`) |
| **Pricing and discounts** | do discounts work? | the page states the SME-confirmed limitation: the data has no discounts |

**RFM in plain words:** score each customer 1 to 5 on **R**ecency (how recently they ordered), **F**requency (how many orders in 90 days) and
**M**onetary (how much they spent in 90 days). VIP = high on all three. Churn Risk = low recency and low frequency. New = recent, few orders, first order within 90 days.
Fixed score bands are used (not equal-sized groups) because 82.5 % of customers have 0 or 1 orders in any 90-day window, and fixed bands mean a score means the same thing every day.

**Full-year figures to quote (from the local full-year run, say so):**

| Figure | Value |
|---|---|
| Customers / total CLV at 31 Dec 2023 | 10,512 / $673,614.04 |
| Snapshot rows (customer × day) | 2,283,740 |
| Segments at 31 Dec 2023 | Churn Risk 7,693 · Regular 1,661 · VIP 755 · New 403 |
| Churn status at 31 Dec 2023 (active / at risk / lapsed) | 2,409 / 1,553 / 6,550 *(check the order on the page before saying it)* |
| Loyalty members | 4,985 (47 %), average CLV $93.12, repeat-order rate 67 % vs 37 % for non-members |

**Say about loyalty:** "Members spend more and come back more, but this shows **association, not proof** that the program causes it."

**Do not claim** anything you cannot see on screen. If a page shows an error, do not record it: tell me and we fix it first.

---

## 6. The data model and daily CLV (about 1.5 minutes)

Show `docs/03_architecture/global-partner-data-model.png` (or describe).

**Star schema** (a design where measurable events sit in the centre and descriptive tables surround them):
- Centre (facts): `fact_order_line` (one row per item line), `fact_order` (one row per order). Two grains so orders are never counted once per item line.
- Around it (dimensions): `dim_customer`, `dim_location`, `dim_item`, `dim_app`, `dim_date`.
- Metrics: `customer_daily_snapshot`, `sales_daily`, `sales_daily_category`, `location_summary`.

**The key table, `customer_daily_snapshot`:** one row per customer per day, from the first order to the last loaded day, **including days without orders**,
because recency and churn status change on those days. Each row holds CLV to date, CLV tier, RFM scores and segment, churn status and loyalty status.

**Say, with the real example from the design document:** "One real customer: 8 May, $12.99, New, active. 25 June, still $12.99, now Churn Risk, at risk. 26 June, they order again:
$34.97, VIP, active. By 31 December, same spend, back to Churn Risk. That evolution is the product."

**Sensitive data:** the loyalty card number stays in silver and never reaches gold or the dashboard.

---

## 7. Quality and failure handling (about 1.5 minutes)

| Protection | What it does |
|---|---|
| **Quarantine** | a row that cannot be used (no key, unreadable timestamp, invalid price) is set aside with every reason it failed. The run continues. No 2023 row hits this today; it protects future loads |
| **25 data-quality checks** | row counts reconcile source → bronze → silver (+ quarantine); revenue is the same in orders, order lines and every aggregate ($746,223.86 for 2023); keys unique; every fact finds its dimensions; quarantine under 1 %; the metric tables tie out to the facts |
| **Retries** | Airflow retries a failed task twice, two minutes apart |
| **Alert** | an EventBridge rule watches Glue jobs; a failed, timed-out or errored job publishes to an SNS topic (email if an address was given at deploy) |
| **Idempotent writes** | MERGE, and a bookmark that only moves on success: rerunning a day never duplicates data |
| **Rollback** | Iceberg keeps earlier table versions; a bad load can be reversed |
| **Audit trail** | every row carries its batch id; `ops.pipeline_runs` records each run's row counts and status |

**Say:** "A bad number should fail loudly, not appear quietly on a dashboard."

---

## 8. Infrastructure, testing and cost (about 1.5 minutes)

- **Infrastructure as code with AWS CDK (Python):** two stacks. `GlobalPartnersData` (KMS key, S3 lake bucket, artifacts bucket, Glue databases, Athena workgroup) and `GlobalPartnersPipeline`
  (network, RDS, Glue jobs, MWAA, dashboard, alerts). One command (`infra/up.sh`) deploys; one (`infra/down.sh`) deletes everything. Every resource is set to be removed with the stack.
- **Local first:** the whole pipeline was built and tested on a laptop with Docker images of the same components AWS runs (SQL Server, Glue 5.1, the MWAA image, Streamlit). Only configuration differs.
- **Tests:** **99 unit tests** (transformations, metrics, dashboard logic and pages) and **21 infrastructure tests** (for example: the dashboard role is read-only, nothing survives a delete). They run in **GitHub Actions** on every push and pull request.
- **Process:** every change goes on a branch, passes CI, and is merged by pull request; nothing is pushed to `main` directly.
- **Cost:** about **$0.42 per hour** while deployed (the always-on pieces: Airflow, the database, the NAT gateway, the load balancer, the dashboard container). Glue and Athena are per use and cost cents here.
  The data is small (55 MB of source files). A single demo deployment is a few dollars; everything is deleted afterwards.

**Say, the honest part (first deploy):** "The first deployment found two bugs the local tests could not: Airflow rejected a logging setting, and the dashboard image could not import its own package.
Both were fixed on branches with new tests, and are in the repository history. That is the value of deploying early."

---

## 9. Limitations and what I would do next (about 1 minute)

Say these yourself before the SME asks. It builds trust.

| Limitation | Why | What production would do |
|---|---|---|
| Dashboard is **HTTP, limited to one IP**, not HTTPS | HTTPS needs a certificate for a domain name, and this project has none. This differs from the approved design; it is logged in `docs/decisions.md` | custom domain + certificate + company sign-in |
| Database traffic trusts the server certificate | the RDS certificate authority is not in Glue's trust store | load the RDS certificate bundle into the job |
| Single-zone database, no backups | demo cost | multi-AZ RDS, backups, point-in-time recovery |
| No discount data, no location names | the source lacks them (SME confirmed) | add them if the source provides them; the model already has the discount columns' place |
| Deleted orders in the source are not detected | the incremental load only sees new and changed rows | SQL Server change data capture |
| Assumptions Q3, Q8, Q10, Q11a, Q16 | not yet confirmed by the SME | each is one setting |

Next steps toward production: branch protection and required CI, linting and dependency scanning, an automated end-to-end test, freshness and volume alarms, a runbook,
table maintenance (compaction), deployment from GitHub with short-lived credentials, per-job least-privilege roles, and a data catalog with retention rules.

---

## 10. Closing (about 30 seconds)

**Say:** "In summary: a pipeline from SQL Server to a dashboard, with daily CLV, 25 automated quality checks, tested code, and infrastructure that I can create or delete with one command.
It runs the same locally and on AWS, and it matches the reference numbers exactly. The remaining questions for you are the five assumptions listed in the design document."

---

## Appendix A: plain-words glossary

| Term | Meaning |
|---|---|
| **ETL / ELT** | Extract, Transform, Load: move data from the source, change it, store it where people can use it |
| **PySpark** | Python interface to Apache Spark, an engine that processes data in parallel |
| **Glue job** | a PySpark script that AWS runs for you on demand and bills per second |
| **Iceberg** | a table format on top of files in S3: gives MERGE, versions and time travel |
| **MERGE** | "insert if new, update if it exists": makes reruns safe |
| **Idempotent** | running it twice gives the same result as running it once |
| **Watermark** | a bookmark of the newest data already loaded |
| **Quarantine** | a side table for unusable rows, with the reasons |
| **Star schema** | facts (events) in the middle, dimensions (descriptions) around them |
| **Grain** | what one row means (one order, one order line, one customer-day) |
| **DAG** | Airflow's name for a workflow: tasks with an order and no loops |
| **MWAA** | Amazon's managed Airflow |
| **Athena** | SQL on files in S3; pay per query |
| **Fargate** | run a container without managing a server |
| **ALB** | Application Load Balancer: the public front door that forwards web traffic to the container |
| **CDK / CloudFormation** | write infrastructure in Python; CloudFormation creates it and rolls back on failure |
| **NAT gateway** | lets private resources reach the internet outward only |
| **IAM role** | a set of permissions a service assumes; least privilege = only what it needs |
| **RFM** | Recency, Frequency, Monetary: a standard way to score customers |
| **CLV** | Customer Lifetime Value; here, total spend to date |
| **CI** | continuous integration: tests run automatically on every change |

## Appendix B: questions the SME may ask (short answers)

| Question | Answer |
|---|---|
| Why Iceberg and not plain Parquet? | MERGE for safe reruns, table versions for rollback, and Athena reads it natively. Needed for the failure-reload requirement |
| Why a snapshot row for every day, even with no orders? | recency and churn status change on those days; without them you cannot show a customer drifting to "at risk" |
| Why not equal-sized RFM groups? | most customers have 0 or 1 orders in 90 days, so equal groups are impossible, and fixed bands mean the same thing every day |
| What if the SME's answer to an assumption differs? | change one setting in `business_rules.yaml` (or one rule) and rerun gold; the effect on 2023 is documented in the design (for example Q3: revenue $2,739.90, or 0.37 %, lower) |
| What if a run fails at 3 am? | Airflow retries twice; if it still fails an SNS alert is sent; the dashboard keeps the last good data; the next run re-reads what was missed |
| How do you know the AWS run is correct? | the same three days give the identical counts locally and on AWS, and 25 checks reconcile the layers |
| Why HTTP on the dashboard? | no domain, so no certificate; access is limited to one IP; production would use HTTPS and sign-in |
| What does it cost to run? | about $0.42 per hour while deployed; deleted after the demo |
| Is the loyalty effect real? | it is an association; we cannot prove cause from this data |
| Where is each decision recorded? | `docs/decisions.md`, with the reason for each |
