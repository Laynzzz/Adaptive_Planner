# Deployment and local release

The local release is verified independently from hosted CI and AWS. No AWS resources have been created, no image has been pushed and no cloud allowance has been approved. See [evidence/status](evidence/cloud-release.md), [cost proposal](deployment/cost-estimate.md), [Terraform state bootstrap](deployment/terraform-state.md) and [incident rehearsal](evidence/incident.md).

## Local images

`Dockerfile` uses digest-pinned Node, uv and Python stages. The frontend is built once and served by FastAPI from `/app/web`, after API/health routes. The runtime is UID/GID 10001, has no Node or build toolchain, and supports a read-only root filesystem with a writable scratch directory. The image's default command is the API; workers use the same image with `python -m planner.jobs.worker`, `planner.ai.worker` or `planner.calendar.worker`.

```powershell
docker build --target runtime --build-arg REVISION=local-review -t adaptive-planner:local-r4 .
.\.tools\bin\uv.exe run python scripts/deployment/prepare_prior_image.py --base-ref e8c51dd
.\.tools\bin\uv.exe run python scripts/deployment/local_rehearsal.py
```

The rehearsal requires the normal local PostgreSQL container. It creates two randomly named databases, migrates populated prior schema 14 to head 16, tests prior-image behavior, takes a custom-format `pg_dump`, restores into the second database and compares every public table's logical records. It exercises an old-business-code command with idempotent replay, solve and activation; image HTTP checks verify readiness, HTML and unauthenticated API rejection. Both temporary databases are removed. The synthetic dump and build contexts remain ignored under `.runtime`; the source application database is never restored over or deleted.

The unmodified R2 image correctly fails readiness after a newer migration. The prior **bridge** image adds only the generic schema-reader check and the optional static-frontend packaging shim; its R2 business/auth/solver/worker code is unchanged. Deploy this bridge before relying on it for rollback. Migration 16 declares which reader schema heads have been tested and binds that declaration to the exact live head. Future migrations must update the marker with a tested reader list; an unknown future head fails readiness. Image rollback never repairs deleted data.

## AWS reference profile, prepared only

Region: us-east-1. One API task (0.5vCPU/1GiB), one CPU worker (2vCPU/4GiB), one interpretation worker and one calendar worker (each 0.25 vCPU/1GiB). Each task includes a bounded OTel sidecar. RDS PostgreSQL 17.9 is private, single-AZ db.t4g.micro with 20 GiB encrypted gp3 and seven-day backups. This is a small demonstration profile, not a highly available production service.

An HTTPS ALB reaches API port 8000 through security groups. Fargate tasks have public outbound IPs to avoid a NAT gateway; their inbound access is restricted to the ALB security group. RDS accepts 5432 only from tasks and has no public route. A short root init container sets only the ephemeral scratch volume's permissions; the application runs as UID10001 with a read-only root. No SSH or ECS Exec is configured.

Cognito Essentials is the selected reference OIDC provider: authorization-code/PKCE, public client, admin-created users, HTTPS callback `${origin}/api/v1/auth/callback`, and one application origin for UI/BFF. Local Keycloak remains the tested development provider. A real domain and regional ACM certificate ARN are required inputs; DNS/certificate ownership is not fabricated. Cloud Cognito login remains unexecuted. Live model and Google Calendar calls are disabled by the reference environment.

ECR tags are immutable; ECS task definitions use image digests. S3 artifacts are private, versioned and KMS-encrypted. Secrets Manager stores an application password separately from RDS's managed master secret. Only the explicit migration task receives the elevated database password, runs Alembic and grants the application role data access without schema-marker writes. Terraform state contains sensitive generated password material: its encrypted, restricted backend is a prerequisite, not an optional afterthought.

CloudWatch receives redacted logs, metrics and X-Ray traces through OTel. Queue/database/ALB alarms target an SNS email subscription, which the approved recipient must confirm. AWS Budgets notifications are configured and are **not spending caps**. Cloud collector, IAM, SMTP/SNS delivery and alarms are prepared and statically validated; none have been tested against AWS.

## Approval and release sequence

Before creating resources, review the cost proposal, account, tags, budget/time window, retained-resource inventory, domain/certificate and a redacted Terraform plan. Configure a protected GitHub `release` environment with required reviewers. The Terraform module defaults service counts to zero, but ALB/RDS/storage would still incur costs after an apply.

1. Bootstrap the encrypted state bucket separately. Copy `demo.tfvars.example` and fill reviewed values. Run `terraform init` with the backend file, then review `terraform plan`; do not treat validation or the offline mock plan as an approved real plan.
2. After explicit approval, provision the reference resources with service counts zero. Supply the first reviewed immutable image digest. ECR repository bootstrap and initial push require the approved operator identity before the generated release role can be used.
3. Save `terraform output -json` as the protected environment's `TERRAFORM_OUTPUTS_JSON`; set `AWS_RELEASE_ROLE_ARN`. The role trusts only the exact repository's `environment:release` OIDC subject, never arbitrary pull requests.
4. Complete the explicitly approved [one-time bootstrap](deployment/bootstrap.md): run the migration task, start only the API, create the dedicated synthetic Cognito account and perform a read-only real login to discover its application owner ID. This starts billable runtime before normal release verification and is not a healthy-release claim. Store its credentials as `RELEASE_SMOKE_USERNAME/PASSWORD` secrets and its ID as `RELEASE_SMOKE_OWNER_ID`. The normal smoke aborts before mutation if the owner does not match. This account must contain synthetic release-test data only.
5. Manually dispatch `.github/workflows/release.yml`. It builds/scans/pushes a unique immutable tag containing the commit SHA, GitHub run ID and attempt number (so reruns cannot collide), resolves the digest, registers an explicit migration task and checks its successful exit before updating any service. Then it waits for service health and runs real OIDC → create → generate → inspect → activate → visible frontend smoke.
6. Failure restores every previous task definition and count, waits for stable services, re-reads the complete service inventory to verify every original definition/count, and repeats workflow smoke before claiming recovery. The controlled-failed-smoke input rehearses this path after a healthy baseline exists. Initial release has no prior healthy deployment and reports that distinction. ECS circuit-breaker rollback is also explicitly enabled; workflow rollback is still needed for failures that pass health checks.
7. Record raw redacted hosted output, image digests, migration/task-definition revisions, workflow smoke and rollback outcome. These steps are presently **NOT EXECUTED**.

The smoke cancels only its own `R4_RELEASE_SMOKE` tasks and uses the dedicated account's work hours; it does not publish to Google or make live model calls. CI/browser call logs are not dumped with credentials. The release helper's rollback control flow has fake-AWS unit coverage; that does not establish a working cloud deployment.

## Restore and cleanup

For a cloud backup rehearsal, restore an RDS snapshot to a **new** isolated instance/subnet/security group, attach an isolated app task with its own secret, compare logical records and run the synthetic workflow. Never overwrite the source instance. Record the snapshot ID, restore timing, comparison, smoke and teardown. This remains NOT EXECUTED; the separate local pg_dump/restore rehearsal is the available evidence.

After an approved demo, scale tasks to zero, remove the ALB and other transient resources through reviewed Terraform changes, and explicitly inventory anything retained: final RDS snapshot, S3 object versions, ECR rollback images, Secrets Manager recovery windows, KMS keys, Cognito pool, logs and state bucket. Deletion protection and `force_destroy=false` deliberately prevent accidental cleanup of retained data. Decide retention before disabling those guards. Stopping RDS is temporary and does not eliminate storage charges; deleting an image is not deleting its data backups.

Current billable AWS inventory: **none created by this task**. Local observability containers, three local image tags, Trivy database cache and synthetic ignored backup/context files remain on this machine; they have no AWS bill.
