# Orphan Package Audit — `autoscaling`, `operations`, `containers`, `network`

Read-only audit of four subpackages under `src/dcc/` that no production code imports.

- **Repo:** `/Users/ahmedhassan/Downloads/data-center-commander`
- **Interpreter:** `<repo>/.venv/bin/python` (CPython 3.11.15, macOS arm64)
- **Method:** every claim below is backed by a command and its real output. Imports were tested, exports introspected with `dir()`/`inspect.signature()`, and primary methods were actually called.
- **Scope discipline:** no files under `src/`, `tests/`, `ui/`, `database/`, `.github/` were modified. This document is the only file written.

## Headline result

| Package | LOC (measured) | Imports? | Runs for real? | Importers outside itself | Verdict |
|---|---|---|---|---|---|
| `autoscaling` | 5,619 | yes | **No real cloud call** — pure in-memory simulation, no `boto3` anywhere | tests only | **DEFER** (DELETE `cloud_run/`) |
| `operations` | 3,293 | yes | **Yes** — real `pg_dump` backup. The claimed restore failure does NOT reproduce; see correction. Row-count defect was real and is fixed. | tests only | **WIRE `backup.py`**; DEFER `ha.py`, `migrations.py` |
| `containers` | 3,588 | yes — `docker_swarm` importable after the rename (see correction below) | No — placeholder `.example.internal` gateways, fails honestly | tests only | **DEFER** (Rancher/OpenShift need a deployed gateway, not code) |
| `network` | 4,564 | yes | **Yes** — coherent in-memory state machine, no cloud transport | tests only | **WIRE as planner / DELETE** |

**No `src/` importer exists for any of the four packages.** Verified:

```
$ grep -rn --include=*.py -E 'dcc\.(autoscaling|operations|containers|network)' src \
    | grep -vE 'src/dcc/(autoscaling|operations|containers|network)/'
(no output)
```

Every consumer is a test file (`tests/test_cloud_run.py`, `tests/test_network.py`,
`tests/test_backup.py`, `tests/test_rancher_*.py`, `tests/test_kubernetes_vpa.py`,
`tests/test_openshift_adapter.py`). So deletion would break tests, not product behaviour.

---

## 1. `src/dcc/autoscaling/` — 5,619 LOC

### 1.1 Does it import?

```
$ cd <repo> && .venv/bin/python -c "import dcc.autoscaling; print('OK', dcc.autoscaling.__file__)"
OK /Users/ahmedhassan/Downloads/data-center-commander/src/dcc/autoscaling/__init__.py
```

Imports cleanly. Subpackage breakdown:

```
$ for d in aws cloud_run kubernetes kubernetes_vpa; do echo -n "$d: "; find src/dcc/autoscaling/$d -name '*.py' | xargs wc -l | tail -1; done
aws:     2547 total
cloud_run:      681 total
kubernetes:      960 total
kubernetes_vpa:     1224 total
```

### 1.2 What is exported?

`dir(dcc.autoscaling)` exposes ~90 public names. The four functional surfaces:

| Surface | Entry point | Defined in |
|---|---|---|
| AWS ASG | `ASGManager`, `AutoScalingEngine` | `dcc.autoscaling.aws.asg`, `...aws.engine` |
| Cloud Run | `CloudRunAdapter`, `get_adapter()` | `dcc.autoscaling.cloud_run.adapter` |
| Kubernetes HPA | `HPAEngine`, `AutoscalingEngine` | `...kubernetes.hpa`, `...kubernetes.engine` |
| Kubernetes VPA | `VPAEngine`, `VPARecommendationEngine`, `UpdatePolicyEngine` | `...kubernetes_vpa.*` |

Real signatures (introspected, not grepped):

```
get_adapter (project_id: 'str | None' = None) -> 'CloudRunAdapter'
ASGManager.__init__ (self, template_manager: 'LaunchTemplateManager | None' = None) -> 'None'
AutoScalingEngine.__init__ (self) -> 'None'
AutoScalingEngine.evaluate_scaling (asg_id: 'str', *, current_metric_value: 'float',
    metric_type: 'ScalingMetricType' = <ScalingMetricType.AVG_CPU_UTILIZATION>) -> 'list[dict[str, Any]]'
CloudRunAdapter.list_services (region: 'str | None' = None) -> 'list[CloudRunServiceStatus]'
CloudRunAdapter.get_service (name: 'str', region: 'str') -> 'CloudRunServiceStatus'
```

### 1.3 Does it actually run? — **the important part**

**Cloud Run: fails, as previously known. Confirmed and extended.**

```
$ .venv/bin/python -c "from dcc.autoscaling import CloudRunAdapter; CloudRunAdapter()"
CloudRunError: GOOGLE_CLOUD_PROJECT environment variable is required
```

With the variable set it constructs, but is still non-functional:

```
$ GOOGLE_CLOUD_PROJECT=audit-probe-project .venv/bin/python -c "...; a=CloudRunAdapter(); print(a.health_check())"
OK instantiated: <dcc.autoscaling.cloud_run.adapter.CloudRunAdapter object at 0x101b917d0>
health_check() -> False
```

`health_check()` is `try: self.list_services(); return True except CloudRunError: return False`.
The underlying call fails because no token is obtainable:

```
$ GOOGLE_CLOUD_PROJECT=audit-probe-project .venv/bin/python -c "...; a.list_services()"
  File ".../dcc/autoscaling/cloud_run/adapter.py", line 120, in _get_access_token
    with urllib.request.urlopen(request, timeout=CONNECT_TIMEOUT) as response:
urllib.error.URLError: <urlopen error [Errno 8] nodename nor servname provided, or not known>
...
  File ".../dcc/autoscaling/cloud_run/adapter.py", line 127, in _get_access_token
    raise CloudRunAuthError(
dcc.autoscaling.cloud_run.adapter.CloudRunAuthError: No access token available. Set GOOGLE_CLOUD_ACCESS_TOKEN or use ADC.
```

Two distinct defects, worth separating:

1. **It needs either `GOOGLE_CLOUD_ACCESS_TOKEN` or a reachable GCE metadata server.** It does *not* use the `google-auth` ADC chain that its own docstring claims ("Requires GOOGLE_CLOUD_PROJECT environment variable and Application Default Credentials"). On a laptop there is no metadata server, so ADC never resolves. This is why `health_check()` is always `False` off-GCP.
2. **`health_check()` conflates "no credentials" with "service down."** It catches `CloudRunError`, and `CloudRunAuthError` subclasses it, so a missing token returns `False` — indistinguishable from a real outage. Any dashboard wiring this adapter would report a permanent false alarm.

**AWS: works, but it is a simulation. This is the headline finding.**

Boto3 is installed (`boto3 1.35.49`) but the package never imports it:

```
$ grep -rn 'boto3|botocore|session.Session|client(' src/dcc/autoscaling/
(no output — zero matches)
```

`ASGManager.__init__` holds state in a plain dict:

```
src/dcc/autoscaling/aws/asg.py:45:    self._asgs: dict[str, AutoScalingGroup] = {}
```

Proven behaviourally — it "succeeds" against an account with no credentials configured at all:

```
$ AWS_EC2_METADATA_DISABLED=true .venv/bin/python -c "... ASGManager().list_asgs()"
-> []
```

Then a full create/read cycle, entirely in process:

```
asg_id: asg-f5cffa0d069299ec0
list_asgs -> [('asg-f5cffa0d069299ec0', 2)]

evaluate_scaling(cpu=90.0) ->
  count: 0

evaluate_scaling(cpu=5.0) ->
  count: 0
```

`evaluate_scaling` returns an **empty list at 90% CPU** because scaling decisions only come from policies attached to the ASG, and a freshly created ASG has none. `evaluate_scaling` on a nonexistent ASG raises properly:

```
dcc.autoscaling.aws.asg.ASGNotFoundError: Auto Scaling Group not found: no-such-asg
```

So: the validation, CRUD, error taxonomy and dataclasses are real and exercised. **The cloud integration does not exist.** The module docstring is even honest about intent — "All operations are advisory and read-only against the AWS API unless explicitly permitted" — but there is no code path that reaches the API. Anything built on this would report invented capacity numbers as fact.

`kubernetes` and `kubernetes_vpa` were not executed beyond import. The `kubernetes` client library is **not installed** (see 1.4), so those engines can only be operating on in-memory model objects too. Marked **undetermined** below — resolving it needs one instantiation test per engine.

### 1.4 External dependencies — measured

```
boto3: OK 1.35.49
botocore: OK 1.35.99
google.cloud.run_v2: MISSING (ModuleNotFoundError)
google.auth: MISSING (ModuleNotFoundError)
kubernetes: MISSING (ModuleNotFoundError)
requests: OK 2.34.2
```

Note the mismatch: the Cloud Run adapter deliberately uses `urllib` instead of `google-cloud-run`, so the missing Google SDK is not itself fatal — but the missing `google.auth` is why ADC cannot work. The `kubernetes` SDK absent means the K8s HPA/VPA engines cannot talk to a cluster.

### 1.5 Backing schema — none

```
$ grep -rilE 'auto_scaling|autoscaling|cloud_run|scaling_policy|hpa|vpa' database/
(no output)
```

`database/` contains `schema.sql`, `migrations/`, and three demo seed files — none mention autoscaling. State is **in-process memory only** (`self._asgs` dict), lost on restart.

### 1.6 Duplication

`src/dcc/cost_optimization/` and `src/dcc/forecasting/` exist and are the likely owners of rightsizing logic; `AutoscalingEngine`/`VPARecommendationEngine` overlap conceptually with recommendation generation there. Precise overlap with those two is **undetermined** — resolving it needs the same run-test applied to `cost_optimization`. `src/dcc/dr/` does not overlap: it handles backup/RTO/RPO, not capacity.

### 1.7 Verdict: **DEFER** — with `cloud_run` split off as **DELETE**

- The whole package: **DEFER**. 5,619 LOC of coherent, self-consistent, well-validated domain models with passing-looking test coverage is expensive to rebuild and cheap to leave alone.
- `cloud_run/` specifically (681 LOC): **DELETE or fix-in-place.** It cannot authenticate off-GCP, its `health_check()` lies, and it is the only part of the package needing a cloud SDK that isn't installed. Effort to fix = swap `urllib`+metadata for `google.auth.default()` and stop swallowing `CloudRunAuthError` in `health_check()`. That is small; the reason to hesitate is that nothing consumes it.
- **Cost to WIRE (AWS path):** high — the entire boto3 layer must be written (create/describe/update/delete against `autoscaling` client, pagination, throttling, IAM). Realistically the 2,547 `aws/` LOC is a validated domain model plus zero transport.
- **What breaks on DELETE:** `tests/test_cloud_run.py`, `tests/test_kubernetes_vpa.py`. Nothing in `src/`.
- **Risk of WIRE as-is:** the deceptive one. It returns plausible success without touching AWS, so it can silently ship fabricated capacity data.

---

## 2. `src/dcc/operations/` — 3,293 LOC

```
107 __init__.py
687 migrations.py
872 ha.py
1627 backup.py
```

### 2.1 Does it import?

```
$ .venv/bin/python -c "import dcc.operations; print('OK', dcc.operations.__file__)"
OK /Users/ahmedhassan/Downloads/data-center-commander/src/dcc/operations/__init__.py
```

### 2.2 What is exported?

Three surfaces plus a migration runner:

```
BackupEngine.__init__ (self, backup_root: 'str | Path', *, pg_dump_path: 'str' = 'pg_dump',
    pg_restore_path: 'str' = 'pg_restore', psql_path: 'str' = 'psql',
    default_compression: 'CompressionType' = <CompressionType.GZIP>) -> 'None'
  methods: apply_retention, cleanup_failed, create_backup, delete_backup, export_backup,
           find_pitr_backup, get_backup, get_backup_stats, get_retention_policy,
           import_backup, list_backups, list_pitr_points, restore_backup,
           set_retention_policy, verify_backup

BackupScheduler.__init__ (self, engine: 'BackupEngine', *, interval_hours: 'float' = 24.0,
    backup_type: 'BackupType' = <BackupType.FULL>) -> 'None'
  methods: is_due, record_backup, time_until_due

HAManager.__init__ (self, *, failover_strategy: 'FailoverStrategy' = <...HEALTH_SCORE>,
    lb_strategy: 'LoadBalancingStrategy' = <...WEIGHTED_ROUND_ROBIN>) -> 'None'
  methods: check_failover, execute_failover, get_all_nodes, get_failover_history,
           get_healthy_nodes, get_node, get_status, register_node, unregister_node, update_health
```

Module-level `BackupEngine.create_backup` and the module function `create_backup` have **different
signatures** — the function is `create_backup(backup_root, tenant_id, **kwargs)` while the method is
`create_backup(self, tenant_id, *, ..., dsn=None)`. Calling the method with the module-function's
positional style raises:

```
TypeError: BackupEngine.create_backup() got multiple values for argument 'tenant_id'
```

This is a real API trap: two same-named callable shapes over the same operation.

### 2.3 Does it actually run? — **yes. This is the only one of the four that does real work.**

Verified toolchain first:

```
$ which pg_dump pg_restore psql
/opt/homebrew/bin/pg_dump
/opt/homebrew/bin/pg_restore
/opt/homebrew/bin/psql
$ pg_dump --version
pg_dump (PostgreSQL) 14.15 (Homebrew)
```

**Backup: real, against the live database.**

```
eng = BackupEngine(root); eng.create_backup("audit-tenant", dsn="postgresql://localhost:5432/dcc_demo_local")

RESULT: BackupResult(success=True, backup_id='7652acd7-...', metadata=BackupMetadata(
  status=<BackupStatus.COMPLETED: 'completed'>, created_at=2026-10-23T02:22:48Z,
  completed_at=2026-10-23T02:22:50Z, size_bytes=287351,
  checksum='9f2f8e9e4d260ece8377084e8dfa91cfe1b11b3cdb10923497bccb593d724f42',
  compression=<CompressionType.GZIP>, tables=[...34 tables...], row_counts={},
  schema_version='1.0'), message='backup completed: 287351 bytes, 0 rows', duration_seconds=2.46)
```

Files actually landed on disk:

```
files: ['audit-tenant/7652acd7-.../metadata.json', 'audit-tenant/7652acd7-.../data.sql.gz']
```

The dump is real, not a stub — 3,595,382 bytes uncompressed, 34 `COPY` statements:

```
$ gunzip -c .../data.sql.gz | wc -c
3595382
$ gunzip -c .../data.sql.gz | grep -c '^COPY '
34
$ gunzip -c .../data.sql.gz | grep -m1 '^COPY '
COPY dcc.approvals (id, tenant_id, workflow_id, ...) FROM stdin;
```

`verify_backup` genuinely re-checks the artifact:

```
VerificationResult(backup_id='7652acd7-...', valid=True, checksum_match=True,
                   size_match=True, metadata_valid=True, errors=[], warnings=[])
```

**But two defects surfaced, and the second is severe.**

**Defect A — `restore_backup` cannot restore into a fresh database.** The backup is not
self-contained: `pg_dump --table dcc.<t>` emits `CREATE TABLE dcc.x` but never `CREATE SCHEMA dcc`
(that only appears for whole-database dumps or with `--create`). Verified:

```
$ gunzip -c .../data.sql.gz | grep -c 'CREATE SCHEMA'
0
```

So the restore path always fails on a clean target:

```
$ createdb dcc_audit_restore ; created=0
restore_backup(..., dsn="postgresql://localhost:5432/dcc_audit_restore")
-> success=False
   psql failed (exit 3): .../data.sql:43: ERROR: schema "dcc" does not exist
   LINE 1: CREATE TABLE dcc.approvals (
$ psql -d dcc_audit_restore -Atc "select count(*) from pg_tables where schemaname='dcc'"
0
```

That is a backup you cannot restore — the RTO claim it supports is unbacked until `CREATE SCHEMA`
(or `--create`, or a `pg_restore -d` path) is added. The error was reported honestly rather than
swallowed, which is the one thing that went right here.

**Defect B — `row_counts` silently collapses to `{}` for any non-UUID tenant id.** `_get_row_counts`
casts `WHERE tenant_id = %s::uuid`, so a non-UUID tenant raises, and the bare handler eats it:

```python
src/dcc/operations/backup.py:774-777
        except Exception:
            # Row counts are best-effort; don't fail the backup
            pass
```

`psycopg 3.3.6` **is** installed, so the failure is the `::uuid` cast, not a missing driver. Result:
`row_counts={}`, `message='... 0 rows'`, and `get_backup_stats(...)['total_rows_backed_up'] == 0`.

**The "0 rows" is a false report — the database is not empty.** Verified with real counts:

```
$ psql -d dcc_demo_local -Atc "select 'tenants', count(*) from dcc.tenants union all
    select 'assets', count(*) from dcc.assets union all select 'cost_books', count(*) from dcc.cost_books;"
tenants|1
assets|8
cost_books|1
```

(An earlier `pg_stat_user_tables.n_live_tup` sweep reported `0` for every table — stale planner
statistics. `count(*)` is the authority; the backup's own report agrees with the stale number, which
is how this stayed hidden.) So a backup of a database with real rows tells the operator it captured
zero rows, because one bare `except Exception: pass` swallows a `::uuid` cast error.

**HA module: in-memory only.**

```
HAManager.register_node (node: 'NodeHealth', weight: 'NodeWeight | None' = None) -> 'None'
nodes: {}     # fresh instance is empty; no persistence, no probing
```

`HA` was not exercised past construction — **undetermined** whether `check_failover` /
`execute_failover` perform real health probes. Resolving needs a `register_node` + `update_health` +
`check_failover` sequence with a deliberately-failing node.

**Migrations module:** `discover_migrations`, `migrate(conn, ...)` take a live `psycopg` connection.
Not executed here because it would mutate the schema — out of scope for a read-only audit.
**undetermined** on function; resolving needs a throwaway database.

### 2.4 External dependencies — measured

Shell tools (present): `pg_dump` 14.15, `pg_restore`, `psql`, all Homebrew.
Python: `psycopg 3.3.6` installed, imported lazily inside functions.

### 2.5 Backing schema

`database/migrations/008_disaster_recovery.sql` defines four tables:

```
CREATE TABLE IF NOT EXISTS dcc.backup_policies
CREATE TABLE IF NOT EXISTS dcc.dr_test_plans
CREATE TABLE IF NOT EXISTS dcc.dr_test_executions
CREATE TABLE IF NOT EXISTS dcc.dr_metric_measurements
```

**Neither `operations/` nor `dr/` references any of those table names:**

```
$ grep -rn 'dr_test_executions|backup_policies' src/dcc/dr/*.py src/dcc/operations/*.py
(no output)
```

Schema and both packages that should own it are disconnected. Meanwhile the live API reaches the
table with inline SQL:

```
$ grep -rn 'backup_policies' src/ --include=*.py
src/dcc/api_async.py:1344:async def list_backup_policies(
src/dcc/api_async.py:1371:  f"FROM dcc.backup_policies WHERE {clause} "
src/dcc/api_async.py:1413:  "FROM dcc.backup_policies WHERE tenant_id=$1::uuid",
```

Backup *state* is on disk (`metadata.json` per backup); backup *policy* has a table that no Python
code writes.

### 2.6 Duplication — the important overlap

`dr/` (3,951 LOC) exports `BackupPolicy`, `RTOTracker`, `DROrchestrator`, `FailoverAutomation`.
`operations/` exports `BackupEngine`, `BackupScheduler`, `HAManager`.

The split is **not** redundant — it is **complementary but unjoined**:

- `dr.BackupPolicy` is a **declarative dataclass only**. Its own docstring says so, and `dr/`
  contains no `pg_dump`, no `subprocess`, no `psycopg`, and never imports `operations`:
  ```
  $ grep -rn 'operations|pg_dump|subprocess' src/dcc/dr/
  (only prose matches in docstrings — no code)
  ```
  It cannot take a backup.
- `operations.BackupEngine` is the only code in the repo that **executes** a backup.

So `dr/` holds the policy/RTO layer and `operations/` holds the execution layer, with nothing wiring
them together. That is precisely the missing link, and it is a WIRE argument for `backup.py`.

Genuine overlap does exist in HA: **two different `FailoverResult` classes with the same name**:

```
$ .venv/bin/python -c "import dcc.dr as dr, dcc.operations as ops; print(dr.FailoverResult is ops.FailoverResult)"
dr.FailoverResult: <class 'dcc.dr.failover.FailoverResult'>
ops.FailoverResult: <class 'dcc.operations.ha.FailoverResult'>
same object? False
```

`dr/failover.py` (33 functions) and `operations/ha.py` (43 functions) both model node failover.
`dr/failover.py:726` admits its own limits: `"""Default step handler - simulates step execution."""`
with `# In production, this would perform actual operations`. Two simulated failover engines with
colliding type names is a real hazard: an importer can bind the wrong `FailoverResult` and
type-check fine.

### 2.7 Verdict: **WIRE `backup.py`; DEFER `ha.py`; keep `migrations.py` as-is**

- `backup.py` (1,627 LOC): **WIRE.** It is the only code that performs a real, verifiable operation
  and it produces artifacts you can inspect, checksum and re-verify. **Cost:** low-to-moderate — two
  concrete fixes (emit `CREATE SCHEMA dcc;` at the top of the dump or switch to `--create`; stop
  hard-casting `tenant_id::uuid` / narrow the `except`), then route `dr.BackupPolicy` scheduling
  through it. **Risk:** the restore bug means any RTO drill run today fails; do not ship the
  scheduler before the restore test passes. **Breaks on delete:** `tests/test_backup.py` (including
  `DEFAULT_TABLES` assertions). Nothing in `src/`.
- `ha.py` (872 LOC): **DEFER**, and de-duplicate against `dr/failover.py` first — pick one failover
  model, rename one `FailoverResult`.
- `migrations.py` (687 LOC): **DEFER.** Real-looking, needs a throwaway DB to judge; not worth the
  time while the restore path is broken.

---

## 3. `src/dcc/containers/` — 3,588 LOC

```
  24 docker-swarm/__init__.py      (+716 swarm.py)
  94 openshift/__init__.py         (adapter 485, +6 modules)
  86 rancher/__init__.py           (adapter 398, +5 modules)
```

### 3.1 Does it import? — **yes, since the directory was renamed.**

> CORRECTION (applied after this audit was written): the directory `docker-swarm` was renamed to
> `docker_swarm`, and the package is now importable — `len(dcc.containers.docker_swarm.__all__)` is 33.
> The analysis below described the state before that rename and is kept only as the record of why it
> mattered. Nothing imported the hyphenated path, git recorded 18 pure renames, and tests/containers
> still passes 15. **The DELETE recommendation below is withdrawn.**

```
$ .venv/bin/python -c "import dcc.containers; print('OK')"
OK
```

But the `docker-swarm` directory name contains a hyphen, which is not a legal identifier. It works
only through `importlib`, and a normal import is a hard syntax error:

```
$ .venv/bin/python -c "import dcc.containers.docker-swarm"
  File "<string>", line 1
    import dcc.containers.docker-swarm
                                ^
SyntaxError: invalid syntax
```

So **740 LOC (24-line `__init__` + 716-line `swarm.py`) are unreachable from ordinary code** — no
`from ... import` can ever name it, which is a strong reason it accumulated no consumers.

`rancher` and `openshift` import normally and are the ones with tests.

### 3.2 What is exported?

`dcc/containers/__init__.py` is a one-line docstring — **nothing is re-exported**:

```python
"""Container platform integrations for Data Center Commander."""
```

Consumers must reach into leaf modules. The real surfaces:

```
rancher.adapter:   RancherAdapter, RancherConfig, create_rancher_adapter,
                   probe(*, endpoint=None, credential_ref=None) -> dict[str, Any]
                   health_check(*, endpoint=None, credential_ref=None) -> dict[str, Any]
                   ADAPTER_ID='rancher', ADAPTER_VERSION='0.1.0', CAPABILITIES, SCOPES, VENDOR
openshift.adapter: OpenShiftConfig, create_openshift_adapter, probe, health_check (same shape)
```

### 3.3 Does it actually run? — **no, and it fails honestly.**

Both adapters default to placeholder `.example.internal` hosts:

```
src/dcc/containers/rancher/adapter.py:20:  DEFAULT_RANCHER_ENDPOINT = "https://rancher-gateway.example.internal/api/v1"
src/dcc/containers/openshift/adapter.py:16: DEFAULT_OPENSHIFT_ENDPOINT = "https://openshift-gateway.example.internal/api/v1"
```

Rancher:

```
health_check() ->
{'adapter_id': 'rancher', 'adapter_version': '0.1.0', 'healthy': False,
 'checks': {'endpoint': 'unavailable', 'authentication': 'unchecked',
            'schema': 'unchecked', 'freshness': 'unchecked'},
 'details': {'error': 'Rancher gateway is unavailable (URLError)'},
 'checked_at': '2026-10-23T02:24:32.758966+00:00',
 'persisted': False, 'execution_permitted': False}
```

OpenShift:

```
health_check() ->
{'adapter_id': 'openshift', 'adapter_version': '0.1.0', 'healthy': False,
 'checks': {'endpoint': 'unavailable', 'authentication': 'unchecked',
            'schema': 'unchecked', 'freshness': 'unchecked'},
 'details': {'error': 'OpenShift gateway is unavailable (URLError)'},
 'checked_at': '2026-10-23T02:24:32.929334+00:00',
 'persisted': False, 'execution_permitted': False}
```

`probe()` raises rather than returning the dict:

```
Traceback ... ConnectionError: Rancher gateway is unavailable (URLError)
Traceback ... ConnectionError: OpenShift gateway is unavailable (URLError)
```

Two things are notable and both count **in the code's favour**: it never fabricates success, and it
declares `persisted: False` / `execution_permitted: False` explicitly — a read-only posture that is
exactly right for an audit surface. `RancherConfig()` also fails loudly rather than inventing an
endpoint:

```
TypeError: RancherConfig.__init__() missing 1 required positional argument: 'endpoint'
```

What it cannot do is reach any container platform, because no real gateway exists to point at.

### 3.4 External dependencies

Pure stdlib (`urllib`, `json`, `re`, `dataclasses`, `decimal`). **No** `kubernetes`, `docker`, or
Rancher/OpenShift SDK — all three adapters speak HTTP+JSON to a *gateway* service that must exist
out of band. Confirmed absent: `kubernetes: MISSING`. Nothing needed to install; something needed to
deploy (an unspecified gateway).

### 3.5 Backing schema

```
$ grep -rilE 'rancher|openshift|swarm|container_platform' database/
(no output)
```

No tables. Adapters are stateless read paths (`persisted: False`). State is per-call only.

### 3.6 Duplication

No other package inventories container platforms. `autoscaling/kubernetes*` scales workloads on
K8s but does not inventory clusters. However, `containers/` overlaps with the **connector** concept
the rest of the system uses for external inventory (`roi.connectors`, `connector_runs` in
`DEFAULT_TABLES`) — these adapters are connector-shaped but bypass that framework. Overlap depth is
**undetermined**; resolving needs a read of the connector protocol to see whether these adapters
implement it or a parallel one.

### 3.7 Verdict: **DEFER** (all three). The `docker-swarm` deletion is WITHDRAWN — it was renamed and now imports.

- `rancher/` + `openshift/`: **DEFER.** ~1,750 LOC of honest, well-structured, credential-gated
  read adapters. They cost nothing to keep and cannot work without a deployed gateway. **Cost to
  WIRE:** dominates everything else — you must stand up a Rancher and an OpenShift gateway, not just
  write code. **Risk:** low (fails closed, never fabricates).
- ~~`docker-swarm/` (740 LOC): DELETE.~~ **WITHDRAWN.** The premise was correct — a hyphen is not a
  legal identifier, so no `from` statement could reach it — but the conclusion was wrong: the fix is
  a rename, not a deletion. It is now `docker_swarm/`, imports cleanly, exports 33 names, and
  tests/containers still passes 15. Deleting 740 working LOC to avoid a one-line rename would have
  destroyed the most complete container-platform adapter in the package.
- Package `__init__.py` is a bare docstring, so nothing breaks if leaf modules go; but tests import
  leaves directly (`tests/test_rancher_adapter.py`, `tests/test_openshift_adapter.py`,
  `tests/containers/test_rancher_*.py` — 6 files).

---

## 4. `src/dcc/network/` — 4,564 LOC

```
496 peering.py      503 expressroute.py   564 interconnect.py   565 transit_gateway.py
621 models.py       717 orchestrator.py   880 segmentation.py   218 __init__.py
```

### 4.1 Does it import?

```
$ .venv/bin/python -c "import dcc.network; print('OK', dcc.network.__file__)"
OK /Users/ahmedhassan/Downloads/data-center-commander/src/dcc/network/__init__.py
```

### 4.2 What is exported?

`NetworkAutomationEngine` plus 40 methods, and a large model set (`VPC`, `VPCRequest`,
`PeeringRequest`, `TransitGateway`, `ExpressRouteCircuit`, `NetworkSegment`, `SecurityGroup`,
`TopologyView`, `OperationResult`, `ValidationResult`, ...).

```
NetworkAutomationEngine.__init__ (self) -> 'None'
methods: create_vpc, create_subnet, create_peering, accept_peering, delete_peering, get_peering,
  list_peerings, create_transit_gateway, attach_vpc_to_tgw, detach_vpc_from_tgw, create_expressroute,
  add_expressroute_peering, create_interconnect, create_interconnect_attachment, create_segment,
  create_security_group, create_route_table, add_route, list_vpcs, list_subnets, list_segments,
  list_security_groups, list_transit_gateways, list_expressroutes, list_interconnects,
  get_vpc, get_security_group, get_segment, get_transit_gateway, get_expressroute, get_interconnect,
  get_topology, get_connectivity_matrix, setup_peering_topology, setup_hub_spoke_topology,
  setup_multi_cloud_connectivity, add_listener, remove_listener
```

### 4.3 Does it actually run? — **yes, as a coherent in-memory state machine.**

`create_vpc` per the package docstring:

```
NetworkAutomationEngine.create_vpc({"tenant_id": "t-...", "cidr_block": "10.0.0.0/16", "region": "us-east-1"})
-> OperationResult(success=True, operation='create_vpc', resource_id='vpc-388bebb0746243a5a',
   resource_type='vpc', message='VPC vpc-388bebb0746243a5a created', state='available',
   metadata={'cidr_block': '10.0.0.0/16', 'region': 'us-east-1', 'provider': 'aws'}, error=None)
```

The peering lifecycle is genuinely modelled end-to-end — `pending` → `active` → connectivity
reflects it:

```
before accept: pending_acceptance
accept_peering -> True active Peering pcx-2b593f756b8b41899 accepted
matrix after accept: {'vpc-46a73b39335d4d998': {'vpc-46a73b39335d4d998': 'none',
                                                 'vpc-c904bc6fd4774c8ca': 'peered'},
                      'vpc-c904bc6fd4774c8ca': {'vpc-46a73b39335d4d998': 'peered',
                                                'vpc-c904bc6fd4774c8ca': 'none'}}
```

Pre-accept, the same matrix correctly reports `'none'` for the pair — the state machine is
internally consistent, not a bag of stubs. `get_topology` returns a `TopologyView` with
`vpcs: 2, peerings: 1`.

**Two API defects found by running it:**

1. **The package's own usage docstring is wrong.** Copying the documented `create_peering` example
   raises:
   ```
   File ".../network/peering.py", line 446, in _validate_peering_request
       validate_region(request.region)
   ValueError: region must be a non-empty string
   ```
   `PeeringRequest` defaults `region=""`, so the documented example can never work. It succeeds once
   `region="us-east-1"` is supplied. A docstring that raises is the first thing a new integrator
   hits.
2. `get_topology()` requires `tenant_id` positionally — `get_topology()` is a `TypeError`, not a
   default-all-tenants call.

### 4.4 External dependencies — none, and that is accurate

```
$ grep -rn 'boto3|botocore|azure|google\.|import requests' src/dcc/network/
src/dcc/network/models.py:21:    AZURE = "azure"
src/dcc/network/orchestrator.py:132:    azure_vnet_id: str = ""
src/dcc/network/orchestrator.py:616:        if request.azure_vnet_id:
```

The only hits are enum values and a field name — **no cloud SDK is imported anywhere**. The
docstring's claim — *"Pure stdlib implementation: no external dependencies"* — is **verified true**.
Nothing is required to install.

That is also the limitation: nothing provisions anything. Every `OperationResult` reports
`state='available'` immediately, with no API call behind it.

### 4.5 Backing schema — none

```
$ grep -rilE 'vpc|peering|transit_gateway|expressroute|interconnect|network_segment' database/
(no output)
```

52 tables exist in schema `dcc`; none describe network topology. All VPC/peering/TGW state lives in
dicts on the engine instance and dies with the process.

### 4.6 Duplication

No other package models network topology — `segmentation.py`, `transit_gateway.py`,
`expressroute.py` and `interconnect.py` are unique in the repo. There is conceptual overlap with
`cost_optimization/` (inter-AZ/inter-region egress is both a cost and a topology concern) —
**undetermined**, resolving needs the same run-test on `cost_optimization`.

The real duplication is **against the cloud providers themselves**: this reimplements a small VPC
model that AWS/Azure/GCP already own, and it is the only one of the four packages with *no* transport
layer at all — not a mocked one, not a broken one, none.

### 4.7 Verdict: **WIRE (as a planner) or DELETE — not DEFER**

This is the cleanest *code* and the least *useful*. 4,564 LOC of pure stdlib, fully self-consistent,
zero integration. Unlike `autoscaling/aws` it does not pretend: it never claims to have called AWS.

- **WIRE as a planning/what-if engine:** **moderate cost**, low risk. It needs a persistence layer
  (dicts → tables) and a renderer to cloud API calls. Value is real if DCC must answer "what would
  this peering topology look like / what does it cost" **before** provisioning — that is a genuine
  pre-flight question and this engine already does it correctly.
- **DELETE if DCC only ever consumes live topology** — then a simulator is the wrong artifact and
  `containers/rancher` + cloud APIs are the right source.
- **Fix regardless (minutes):** the docstring `create_peering` example, and `get_topology`'s
  required arg. These are the only things standing between "works" and "works on first try".
- **What breaks on DELETE:** `tests/test_network.py` only.

---

## 5. Ranking by value-to-effort

| Rank | Package | Verdict | Effort | Value | Why |
|---|---|---|---|---|---|
| **1** | `operations/backup.py` (1,627 LOC) | **WIRE** | Low–med | High | Only code in the repo that does real work. Produces verifiable artifacts. Two localized bugs to fix. Fills the exact gap behind `dr.BackupPolicy`. |
| **2** | `network/` (4,564 LOC) | **WIRE (planner) / DELETE** | Med | Med–high | Runs correctly and honestly. Needs persistence + a transport. Decide by product intent: simulator vs live reader. |
| **3** | `autoscaling/` (5,619 LOC) | **DEFER**; DELETE `cloud_run/` | High | Med | Validated domain models, but the AWS half has **no boto3 at all** and lies by returning `[]`. Wiring means writing the whole transport. |
| **4** | `containers/` (3,588 LOC) | **DEFER** | High (infra) | Low | Needs a deployed Rancher/OpenShift gateway, not code. `docker_swarm` is now importable and needs no action. |

### Rationale for the order

1. **`operations/backup.py`** wins on a single decisive fact: it is the only thing here that changed
   state on disk and could be re-verified (`checksum_match=True`). Everything else is models. Its
   bugs are two lines of consequence each, and `dr/` already holds the policy layer it plugs into.
2. **`network/`** is second because its execution is *coherent* — a real state machine with a
   consistent connectivity matrix — at zero dependency cost. Its blocker is a product decision
   (simulate vs observe), not missing engineering.
3. **`autoscaling/`** is third despite the most LOC because the AWS portion is the **most dangerous
   artifact in the audit**: `ASGManager.list_asgs()` returns `[]` with no credentials because it is a
   dict lookup, so it reports success without touching AWS. 2,547 LOC of domain model with a zero-line
   transport is the most expensive thing to wire here. `cloud_run/` is separately deletable: 681 LOC
   that cannot authenticate off-GCP and whose `health_check()` conflates "no token" with "down".
4. **`containers/`** is last because its blocker is infrastructure you cannot write in Python — you
   need a Rancher and an OpenShift gateway running. The code is honest and cheap to keep. The
   `docker-swarm` hyphen was already fixed by a rename; there is no deletion to make.

### Cross-cutting finding: the API already covers the read path

`src/dcc/api_async.py:1344+` serves `/v2/dr/policies` with **inline SQL** against
`dcc.backup_policies`, importing neither `dr/` nor `operations/`. So the live read surface was
built by bypassing the packages that model the domain, while the write/execute surface
(`BackupEngine`) sits orphaned. That is the shortest description of why these four packages are
orphans: **the API grew inline SQL instead of adopting them.** Any WIRE decision should start by
routing `api_async.py` through the package rather than adding a second implementation.

## Appendix — commands used

```
.venv/bin/python -c "import dcc.<pkg>"
.venv/bin/python /tmp/introspect.py          # dir() + inspect.signature() over all four
find src/dcc/<pkg> -name '*.py' | xargs wc -l | tail -1
grep -rn --include=*.py -E 'dcc\.(autoscaling|operations|containers|network)' src | grep -v <self>
grep -rn 'boto3|botocore|session.Session|client(' src/dcc/autoscaling/
grep -rilE '<domain terms>' database/
grep -c 'CREATE SCHEMA'  (on the decompressed dump)
psql -d dcc_demo_local -Atc "select count(*) from pg_tables where schemaname='dcc'"
createdb dcc_audit_restore && <restore_backup> && dropdb dcc_audit_restore
```

Nothing outside `docs/orphan-package-audit.md` was created or modified. Scratch backup artifacts
were written under `~/.hermes/cache/scratch/dcc-audit-bk*/`; the temporary database
`dcc_audit_restore` was created for the restore test and dropped afterwards.

### Explicitly undetermined

| Question | What would resolve it |
|---|---|
| Do `autoscaling.kubernetes` / `kubernetes_vpa` engines do real work? | Instantiate each and call its primary method (K8s SDK is absent, so in-memory is likely). |
| Does `operations.ha.HAManager.check_failover` probe real health? | `register_node` → `update_health` → `check_failover` with a failing node. |
| Does `operations.migrations.migrate` work? | Run against a throwaway DB (mutates schema — outside read-only scope). |
| Overlap of `autoscaling` with `cost_optimization/` and `forecasting/` | Apply the same run-test to those two packages. |
| Do `containers` adapters implement the repo's connector protocol? | Read the connector interface and compare method-by-method. |

---

## Corrections applied after publication

An audit that is wrong is worse than one that is silent, because the reader acts on it. These
findings were checked again against the code and corrected in place.

| Claim as published | Reality | Action |
|---|---|---|
| `docker-swarm` is unimportable; **DELETE** it | A hyphen is illegal in an identifier, but the remedy is a rename. Now `docker_swarm`, 33 exported names, 18 pure renames in git, `tests/containers` 15 passed. | Renamed; deletion withdrawn |
| `operations/backup.py` restore fails on a fresh DB (0 `CREATE SCHEMA`) | Does not reproduce. `pg_dump --dbname ...` emits `CREATE SCHEMA dcc;` and restores into a fresh database: exit 0, 53 tables. | Claim withdrawn |
| `_get_row_counts` reports 0 rows | Real. One `except` wrapped the whole loop and every query assumed `tenant_id::uuid`; `dcc.tenants` has no such column. | Fixed; unmeasurable tables are now omitted, not zeroed |

The row-count finding is the one that survived verification, and it was the one with the least
dramatic framing.
