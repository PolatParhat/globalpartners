# Video speaker notes: GlobalPartners Business Insights Pipeline (final)

Audience: the SME. Target length: **12 to 15 minutes**. Record one section at a time; you can cut between sections.
Written in plain words on purpose: read it once end to end and you understand the whole project.
Lines after **Say:** are what to tell the SME (in your own words); the rest is background for you.

**State of the demo (2 November 2026):** the whole of 2023 is loaded on AWS **through the real Airflow pipeline**, all 25 data-quality checks
pass, the numbers match the local reference **to the cent**, and all six dashboard pages work.

---

## 0. Before you press record

**Cost reminder:** everything on AWS costs about **$0.42 per hour** while it exists. Prepare first, record fast, then run `infra/down.sh`.

| Check | How |
|---|---|
| Dashboard opens in the recording browser, on the 31 December date | the link printed by `up.sh` (HTTP, not HTTPS); only your IP can open it |
| Airflow UI open | AWS console → MWAA → globalpartners → Open Airflow UI |
| Airflow shows the green runs | `globalpartners_daily` → Runs (explained in section 4) |
| Four browser tabs, in this order | 1 architecture diagram (`docs/03_architecture/global-partner-pipeline-architecture.png`), 2 Airflow, 3 dashboard, 4 AWS console (CloudFormation → GlobalPartnersPipeline → Resources) |
| Hide private things | do not show the account number, your IP address or your email. Crop or blur the top-right of the AWS console |
| Zoom the browser to 125 % | readable on a recording |
| Close notifications | Slack, mail, calendar |

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
| Test data excluded | the app `Alltown Fresh - DEVELOPMENT` is test traffic (SME confirmed). It is loaded but removed at the metrics layer: this is why 52,641 orders are loaded and 52,015 are counted |
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

## 4. One day of the pipeline, how the year was loaded, and the live demo (about 3.5 minutes)

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

### How the full year got into the system

**Say:** "A real business adds one day at a time. To fill a whole year for the demo, I ran the same Airflow pipeline several times.
First three single days, to prove daily behaviour. Then I added one run setting, `replay_until`, so a single run can replay a range of days
and then run the same six tasks once over everything it received. It is optional: left empty, a run does one day exactly as before."

| Airflow run | Days replayed | Orders added |
|---|---|---|
| 1 | 1 Jan 2023 | 63 |
| 2 | 2 Jan 2023 | 96 |
| 3 | 3 Jan 2023 | 130 |
| 4 | 4 to 31 Jan | 3,661 |
| 5 | 1 Feb to 31 May | 18,831 |
| 6 | 1 Jun to 31 Dec | 29,860 |
| **Total loaded** | the whole year | **52,641** (52,015 counted after removing the test app) |

The first three days give the same counts locally and on AWS: **63 / 120 / 105**, **96 / 159 / 173**, **130 / 184 / 151** (orders / lines / options).

### Live demo steps (tab 4, then tab 2)

1. **AWS console, CloudFormation:** "Everything you see here was created from code by one command." Show the resource list (VPC, RDS, Glue jobs, MWAA, ECS service, load balancer).
2. **Airflow, Graph view of `globalpartners_daily`:** show the six tasks and the green runs. Click a run, open a task log (for example `replay_day`, which prints `replayed … orders, … lines, … options added`).
3. **Trigger form (optional, 20 seconds):** click Trigger DAG w/ config and point at the `replay_until` field: "this is the run setting I added to load the year."

**The proof (say this slowly):** "I did not trust the load, so I counted the result in Athena and compared with the reference I computed from the raw files:"

| Figure | AWS (Athena) | Reference | Match |
|---|---|---|---|
| Orders in scope | 52,015 | 52,015 | yes |
| Revenue | $746,223.86 | $746,223.86 | yes |
| Customers | 10,512 | 10,512 | yes |
| Total CLV at 31 Dec | $673,614.04 | $673,614.04 | yes |
| Snapshot rows (customer × day) | 2,283,740 | 2,283,740 | yes |
| Locations | 20 | 20 | yes |

"Same code, same numbers, to the cent, locally and on AWS. And the 25 checks pass on that run."

---

## 5. The dashboard (about 3 minutes)

Show tab 3. Six pages, one per business question in the requirements. The sidebar **"as of" date** picks the day the customer pages describe;
it defaults to the last day (31 December). Move it to an earlier date once to show that the customer view changes over time.

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

**Figures at 31 December 2023** (read them from the screen while you speak; these are the values to expect):

| Figure | Value |
|---|---|
| Customers / total CLV | 10,512 / $673,614.04 |
| Segments | Churn Risk 7,693 · Regular 1,661 · VIP 755 · New 403 |
| Churn status (three groups: 2,409 / 1,553 / 6,550) | read the labels on the page before you name which is which |
| Loyalty members | 4,985 (47 %), average CLV $93.12, repeat-order rate 67 % vs 37 % for non-members |

**Say about loyalty:** "Members spend more and come back more, but this shows **association, not proof** that the program causes it."

**Say about location names:** "Locations are shown by id because the source has no names (SME confirmed)."

---

## 6. The data model and daily CLV (about 1.5 minutes)

Show `docs/03_architecture/global-partner-data-model.png` (or describe).

**Star schema** (a design where measurable events sit in the centre and descriptive tables surround them):
- Centre (facts): `fact_order_line` (one row per item line), `fact_order` (one row per order). Two grains so orders are never counted once per item line.
- Around it (dimensions): `dim_customer`, `dim_location`, `dim_item`, `dim_app`, `dim_date`.
- Metrics: `customer_daily_snapshot`, `sales_daily`, `sales_daily_category`, `location_summary`.

**The key table, `customer_daily_snapshot`:** one row per customer per day, from the first order to the last loaded day, **including days without orders**,
because recency and churn status change on those days. Each row holds CLV to date, CLV tier, RFM scores and segment, churn status and loyalty status.
For 2023 it has **2,283,740 rows**.

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

**A real example from this deployment (use it):** "When I first switched the DAG on, Airflow started a run for today's date. The data only covers 2023,
so it loaded zero orders, and the data-quality step **failed the run** instead of publishing an empty result. That is the safety net doing its job."
(If that red run is visible in Airflow, point at it.)

**Say:** "A bad number should fail loudly, not appear quietly on a dashboard."

---

## 8. Building it for real: what the first deployment taught me (about 2 minutes)

- **Infrastructure as code with AWS CDK (Python):** two stacks. `GlobalPartnersData` (KMS key, S3 lake bucket, artifacts bucket, Glue databases, Athena workgroup) and `GlobalPartnersPipeline`
  (network, RDS, Glue jobs, MWAA, dashboard, alerts). One command (`infra/up.sh`) deploys; one (`infra/down.sh`) deletes everything. Every resource is set to be removed with the stack.
- **Local first:** the whole pipeline was built and tested on a laptop with Docker images of the same components AWS runs (SQL Server, Glue 5.1, the MWAA image, Streamlit). Only configuration differs.
- **Tests:** **99 unit tests** (transformations, metrics, dashboard logic and pages) and **21 infrastructure tests** (for example: the dashboard role is read-only, nothing survives a delete). They run in **GitHub Actions** on every push and pull request.
- **Process:** every change goes on a branch, passes CI, and is merged by pull request; nothing is pushed to `main` directly.

**Say, the honest part:** "Deploying to the real cloud for the first time found things local tests could not. I fixed each on its own branch, with a test, and merged by pull request:"

| What went wrong | Why | Fix |
|---|---|---|
| Airflow (MWAA) refused to be created | I had switched two log types off without giving them a log level, and the AWS API requires a level even for a switched-off log | set the level; added a test that every log module has one |
| The dashboard page crashed with "No module named dashboard" | Streamlit only adds the script's own folder to Python's search path, not the project root. Locally the setup hid this | set `PYTHONPATH=/app` in the image; tested by loading the page inside the real ARM64 image |
| Loading the whole year in one step hung | one huge database transaction on the smallest database size: it hit the one-hour limit, twice | loaded the year in chunks, each through the same DAG (`replay_until`); bigger chunks turned out faster per order |
| A mistyped date (`2023-04-31`) failed three runs | April has 30 days; the job rejected the date before touching data | failed fast and cheaply; the lesson is to validate inputs where they are entered |

**Say:** "That is the value of deploying early, and of making every failure loud and cheap."

- **Cost:** about **$0.42 per hour** while deployed (the always-on pieces: Airflow, the database, the NAT gateway, the load balancer, the dashboard container). Glue and Athena are per use.
  The whole demo day, including the failed attempts, cost roughly **$9** (estimate from run times; confirm on the AWS bill). Everything is deleted afterwards.

---

## 9. Limitations and what I would do next (about 1 minute)

Say these yourself before the SME asks. It builds trust.

| Limitation | Why | What production would do |
|---|---|---|
| Dashboard is **HTTP, limited to one IP**, not HTTPS | HTTPS needs a certificate for a domain name, and this project has none. This differs from the approved design; it is logged in `docs/decisions.md` | custom domain + certificate + company sign-in |
| Database traffic trusts the server certificate | the RDS certificate authority is not in Glue's trust store | load the RDS certificate bundle into the job |
| Single-zone, smallest database, no backups | demo cost | multi-AZ, larger instance, backups, point-in-time recovery |
| The "shops" are simulated | the source files are a static snapshot, so a replay job feeds them day by day | connect the real point-of-sale database |
| No discount data, no location names | the source lacks them (SME confirmed) | add them if the source provides them; the model already has a place for the discount columns |
| Deleted orders in the source are not detected | the incremental load only sees new and changed rows | SQL Server change data capture |
| Assumptions Q3, Q8, Q10, Q11a, Q16 | not yet confirmed by the SME | each is one setting |

Next steps toward production: branch protection and required CI, linting and dependency scanning, an automated end-to-end test, freshness and volume alarms, a runbook,
table maintenance (compaction), deployment from GitHub with short-lived credentials, per-job least-privilege roles, and a data catalog with retention rules.

---

## 10. Closing (about 30 seconds)

**Say:** "In summary: a pipeline from SQL Server to a dashboard, with daily CLV, 25 automated quality checks, tested code, and infrastructure I can create or delete with one command.
It ran on AWS for the whole of 2023 and matches the reference numbers to the cent. The open questions for you are the five assumptions listed in the design document.
Thank you."

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
| How do you know the AWS result is correct? | the AWS tables match the reference computed from the raw files to the cent (orders, revenue, customers, CLV, snapshot rows), and 25 checks reconcile the layers |
| Why 52,641 orders loaded but 52,015 counted? | 626 orders come from the test app, which is loaded but excluded from every metric (SME confirmed it is test data) |
| How was a year loaded if the pipeline runs daily? | the same DAG, with an optional `replay_until` setting so one run can replay a range of days; normal daily runs are unchanged |
| Why HTTP on the dashboard? | no domain, so no certificate; access is limited to one IP; production would use HTTPS and sign-in |
| What does it cost to run? | about $0.42 per hour while deployed; roughly $9 for the whole demo day; deleted afterwards |
| Is the loyalty effect real? | it is an association; we cannot prove cause from this data |
| Where is each decision recorded? | `docs/decisions.md`, with the reason for each |
