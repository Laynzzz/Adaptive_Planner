# One-time cloud bootstrap (not executed)

This is a separate, explicitly approved operator phase before the first verified release. It solves the first-login dependency: the API must be running before Cognito can return an authenticated application owner ID. It creates no scheduled work and does not claim a healthy full deployment. Use only the reviewed immutable image and dedicated synthetic account. Cloud credentials, cost approval, DNS/TLS and a successful real Terraform apply are prerequisites; none were available or executed during this task.

After Terraform creates resources with service counts zero, save reviewed outputs to `outputs.json`. The migration task and API task definitions must already reference the approved image digest. Run these commands from an approved Bash environment with AWS CLI, jq, Node and installed project browser dependencies:

```bash
set -euo pipefail
cluster=$(jq -r '.cluster.value' outputs.json)
api=$(jq -r '.services.value.api' outputs.json)
origin=$(jq -r '.application_url.value' outputs.json)
jq '{cluster:.cluster.value,taskDefinition:.migration_task.value,launchType:"FARGATE",networkConfiguration:{awsvpcConfiguration:{subnets:.subnets.value,securityGroups:[.task_security_group.value],assignPublicIp:"ENABLED"}}}' outputs.json > bootstrap-migration.json
aws ecs run-task --cli-input-json file://bootstrap-migration.json > bootstrap-started.json
jq -e '((.failures // []) | length)==0 and (.tasks | length)==1' bootstrap-started.json >/dev/null
task=$(jq -r '.tasks[0].taskArn' bootstrap-started.json)
aws ecs wait tasks-stopped --cluster "$cluster" --tasks "$task"
aws ecs describe-tasks --cluster "$cluster" --tasks "$task" > bootstrap-migration-result.json
jq -e '((.failures // []) | length)==0 and (.tasks | length)==1 and (.tasks[0].containers | length)>0 and all(.tasks[0].containers[]; .exitCode==0)' bootstrap-migration-result.json >/dev/null
aws ecs update-service --cluster "$cluster" --service "$api" --desired-count 1 >/dev/null
aws ecs wait services-stable --cluster "$cluster" --services "$api"
curl --fail --silent "$origin/health/ready"
```

Create an admin-managed Cognito synthetic user in the reviewed pool and set its permanent password using the approved operator's console, without placing credentials in a shell command/history. Supply username/password to the following process via an approved secret-injection mechanism as `PLANNER_RELEASE_SMOKE_USERNAME` and `PLANNER_RELEASE_SMOKE_PASSWORD`. Do not turn on shell tracing or Playwright debug logging.

```bash
node scripts/deployment/cloud_smoke.mjs "$origin" --discover-owner
```

This mode performs real OIDC login and GET `/me`; it emits only the returned owner UUID and a zero-planning-mutations marker. First login creates the normal identity/session records. It sends no task, availability, solve, activation or calendar command. Record that returned UUID as protected `RELEASE_SMOKE_OWNER_ID` and credentials as the two protected secrets, then run the normal release workflow. The normal mode requires an exact UUID match before mutation.

On any bootstrap failure, stop this phase, save redacted output and return API desired count to zero. The other three services remain zero. Do not call bootstrap a rollback-verified baseline. If the first normal release fails, its previous inventory may contain only this API; full-workflow rollback verification will correctly fail because the previous solve worker was absent. Fix the release and rerun it; the unique immutable run tag permits this. Only after a full normal release passes is a controlled failed-release/recovery rehearsal meaningful.

```bash
aws ecs update-service --cluster "$cluster" --service "$api" --desired-count 0 >/dev/null
aws ecs wait services-stable --cluster "$cluster" --services "$api"
```

Scaling to zero does not stop ALB, RDS or retained-storage charges. Follow the approved cleanup inventory and time window.
