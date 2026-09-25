# Proposed us-east-1 cost envelope

Checked 2026-09-25 against current official AWS pricing. USD, 730hours/month, Linux x86 Fargate on-demand. No free-tier credits or savings commitments assumed. This is an estimate for review, not authorization or a spending cap.

| Component and assumption | Arithmetic | Estimated/month |
|---|---|---:|
| Fargate API + 3 workers, total 3 vCPU and 7 GiB |730×(3×$0.0404784 +7×$0.004446) |$111.38 |
| RDS PostgreSQL db.t4g.micro single-AZ |730×$0.016 |$11.68 |
| RDS 20 GiB gp3 |20×$0.115 |$2.30 |
| ALB, average 1 LCU |730×($0.0225 +$0.008) |$22.27 |
| Public IPv4, 4 task addresses + 2 ALB addresses |6×730×$0.005 |$21.90 |
| CloudWatch budgeted 300 custom metric series |300×$0.30 |$90.00 |
| Logs 5 GiB, 1 dashboard, 3 standard alarms |5×$0.50 +$3 +3×$0.10 |$5.80 |
| 2 Secrets Manager secrets, 2 customer KMS keys (app+state) |2×$0.40 +2×$1 |$2.80 |
| ECR 2 GiB + S3 small artifacts, allowance |usage-dependent |$0.30 |
| Traces/requests/data transfer/synthetic Cognito allowance |usage-dependent |$2.50 |
| **Estimated continuously running total** |rounded |**about $271/month** |

Fargate's official example gives $0.000011244/vCPU-second and$0.000001235/GiB-second in N. Virginia. [AWS Fargate pricing](https://aws.amazon.com/fargate/pricing/). RDS unit rates were selected directly from the official regional price-list JSON, with product SKUs and publication date preserved in [raw selection](../evidence/raw/aws-rds-price-selection.json); see [RDS PostgreSQL pricing](https://aws.amazon.com/rds/postgresql/pricing/).

ALB assumptions use the hourly and LCU rates on [Elastic Load Balancing pricing](https://aws.amazon.com/elasticloadbalancing/pricing/). Public IPv4 is $0.005/address-hour, including addresses assigned to managed services. [AWS public IPv4 pricing announcement](https://aws.amazon.com/blogs/aws/new-aws-public-ipv4-address-charge-public-ip-insights/).

The deliberately conservative 300-series metrics allowance covers service/status/stage combinations; cardinality and traffic can change the bill. Collection exports no user/job IDs as dimensions. Actual CloudWatch series/ingestion must be measured in the hosted rehearsal and the estimate updated. [CloudWatch pricing](https://aws.amazon.com/cloudwatch/pricing/). Logs retain seven days; X-Ray requests and data transfer are a separate small allowance rather than a measured charge.

Secret storage and KMS key rates come from [Secrets Manager](https://aws.amazon.com/secrets-manager/pricing/) and [KMS](https://aws.amazon.com/kms/pricing/). Small artifact estimates use [ECR](https://aws.amazon.com/ecr/pricing/) and [S3](https://aws.amazon.com/s3/pricing/). The configured identity tier is Cognito Essentials, priced at $0.015/MAU above its applicable free tier; the tiny synthetic-user allowance does not rely on eligibility. [Cognito pricing](https://aws.amazon.com/cognito/pricing/).

Proposed review envelope: an **8-hour rehearsal with a $15 initial allowance**, immediate transient-resource teardown, and a separately approved retention limit. The rough full-profile daily equivalent is $8.91; this cannot guarantee a hard ceiling. The proposed $300 monthly AWS Budgets alarm threshold is only a notification threshold, not permission to spend $300.

Excluded/unbounded items must be approved explicitly if used: domain purchase/DNS beyond an existing zone, larger backup/snapshot retention, burst CPU credits above the RDS baseline, transfer beyond the assumed light traffic, live AI usage, extra environments, longer uptime and taxes. Deployment can temporarily double ECS tasks during rolling replacement. No NAT gateway, Redis or Kubernetes is provisioned. Even with desired_count=0, provisioned ALB/RDS/secrets/storage can continue billing. State and final snapshots can outlive the demo.

Current credentials/allowance: **not supplied; none approved**. Resource creation, image push, hosted rollout, AWS rollback/restore and paid live providers remain unexecuted.
