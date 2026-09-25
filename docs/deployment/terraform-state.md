# Separate Terraform state bootstrap

The application module cannot safely create its own backend while already using that backend. An approved operator first creates a separate state S3 bucket and customer-managed KMS key in us-east-1, then records their names/ARNs outside Git. The state key is included in the proposed cost envelope.

Required properties: bucket public-access blocks, versioning, default SSE-KMS encryption, TLS-only bucket policy, narrowly scoped operator/release access, and retained state/object versions. Enable S3 lockfile support using `use_lockfile=true`; no DynamoDB table is needed by this pinned Terraform 1.16.2 configuration. Keep the bootstrap identity separate from the limited GitHub deployment role.

Copy `infra/terraform/backend.hcl.example` to an ignored local file and fill the approved bucket/KMS ARN. Initialize using `terraform -chdir=infra/terraform init -backend-config=/absolute/path/backend.hcl`. Never commit state, tfvars containing credentials, binary plans or generated secret values. The application role password is sensitive state material even though Terraform redacts it from normal output.

Local verification intentionally uses `init -backend=false`, `validate`, and `terraform test` with mocked AWS/random providers. It contacts the public provider registry to fetch checksum-verified binaries but creates no AWS infrastructure. The provider lockfile pins aws 6.66.0 and random 3.9.1 as resolved locally; read the lockfile for the exact versions rather than inferring them from a machine's globally installed tools.

A real plan needs the approved account/profile, state backend, region/tags, domain/certificate, budget recipient, immutable image digest and Cognito domain prefix. Save its redacted review output before apply. Retain the state bucket until all application resources and intentionally retained objects have been inventoried; destroying the application stack does not remove state or its backups.
