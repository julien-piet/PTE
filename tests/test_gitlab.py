import os
import inspect
import textwrap

from typing import Any, Dict
from dotenv import load_dotenv

load_dotenv()

_gid = lambda type_name: f"gid://gitlab/{type_name}/999999999"

# Placeholder default values for common argument types, to be used when no specific argument is defined.
PROJECT_PATH = "byteblaze/accessible-html-content-patterns"
GROUP_PATH = "byteblaze"

FIXTURES: Dict[str, Any] = {
    "full_path": PROJECT_PATH,
    "project_path": PROJECT_PATH,
    "group_path": GROUP_PATH,
    "namespace_path": GROUP_PATH,
    "text": "hello",
    "content": "stages: [test]\njob:\n  stage: test\n  script: echo hi\n",
    "identifier": "PROJECTS",
    "name": "test-name",
    "title": "Test title",
    "description": "Test description",
    "body": "Test body",
    "key": "TEST_KEY",
    "value": "test_value",
    "queue_name": "default",
    "sha": "0000000000000000000000000000000000000000",
    "ref": "main",
    "source_branch": "feature-branch",
    "target_branch": "main",
    "feature_name": "test_feature",
    "scan_mode": "OPENAPI",
    "target": "https://example.com",
    "api_specification_file": "https://example.com/openapi.json",
    "architecture": "amd64",
    "platform": "linux",
    "url": "https://example.com",
    "endpoint_url": "https://example.com/audit",
    "token": "fake-token",
    "username": "root",
    "emoji": "thumbsup",
    "start_date": "2024-01-01",
    "end_date": "2024-01-07",
    "due_date": "2024-12-31",
    "locked": False,
    "confidential": False,
    "draft": False,
    "id": _gid("Project"),
    "iid": "1",
    "board_id": _gid("Board"),
    "list_id": _gid("List"),
    "group_id": _gid("Group"),
    "project_id": _gid("Project"),
    "namespace_id": _gid("Namespace"),
    "issue_id": _gid("Issue"),
    "note_id": _gid("Note"),
    "epic_id": _gid("Epic"),
    "milestone_id": _gid("Milestone"),
    "label_id": _gid("Label"),
    "runner_id": _gid("Ci::Runner"),
    "pipeline_id": _gid("Ci::Pipeline"),
    "job_id": _gid("Ci::Build"),
    "merge_request_id": _gid("MergeRequest"),
    "snippet_id": _gid("Snippet"),
    "design_id": _gid("Design"),
    "todo_id": _gid("Todo"),
    "vulnerability_id": _gid("Vulnerability"),
    "header_id": _gid("AuditEvents::Streaming::Header"),
    "destination_id": _gid("AuditEvents::ExternalAuditEventDestination"),
    "requirement_id": _gid("Requirement"),
    "work_item_id": _gid("WorkItem"),
    "awardable_id": _gid("Issue"),
    "discussion_id": "fake-discussion-id",
    "policy_name": "test-policy",
    "policy_yaml": "---\nname: test\ntype: scan_execution\n",
    "cadence_id": _gid("Iterations::Cadence"),
    "iteration_id": _gid("Iteration"),
    "oncall_schedule_iid": "1",
    "schedule_iid": "1",
    "rotation_id": _gid("IncidentManagement::OncallRotation"),
    "timelog_id": _gid("Timelog"),
    "tag_id": _gid("IncidentManagement::TimelineEventTag"),
    "timeline_event_id": _gid("IncidentManagement::TimelineEvent"),
    "release_tag": "v1.0.0",
    "link_id": _gid("Releases::Link"),
    "terraform_state_id": _gid("Terraform::State"),
    "corpus_id": _gid("Corpus"),
    "finding_uuid": "00000000-0000-0000-0000-000000000000",
    "security_policy_project_id": _gid("Project"),
    "agent_id": _gid("Clusters::Agent"),
    "token_id": _gid("Clusters::AgentToken"),
    "saved_reply_id": _gid("SavedReply"),
    "annotation_id": _gid("Metrics::Dashboard::Annotation"),
    "environment_name": "production",
    "container_repository_id": _gid("ContainerRepository"),
    "package_id": _gid("Packages::Package"),
    "package_file_id": _gid("Packages::PackageFile"),
    "upload_id": _gid("Upload"),
    "cluster_agent_id": _gid("Clusters::Agent"),
    "source_global_id": _gid("Issue"),
    "target_global_id": _gid("Issue"),
    "custom_emoji_id": _gid("CustomEmoji"),
    "compliance_framework_id": _gid("ComplianceManagement::Framework"),
    "namespace_ban_id": _gid("NamespaceBan"),
    "resource_link_id": _gid("IssuableResourceLink"),
    "alert_iid": "1",
    "site_profile_id": _gid("DastSiteProfile"),
    "scanner_profile_id": _gid("DastScannerProfile"),
    "profile_id": _gid("DastProfile"),
    "site_token": "fake-site-token",
    "normalized_target_url": "https://example.com",
    "strategy": "TRIGGER_ADDRESS",
    "http_integration_id": _gid("AlertManagement::HttpIntegration"),
    "escalation_policy_id": _gid("IncidentManagement::EscalationPolicy"),
    "issue_iid": "1",
    "note": "1h",
    "spent_at": "2024-01-01",
    "summary": "Test summary",
    "assignee_usernames": ["root"],
    "ids": [_gid("Project")],
    "event_type_filters": [["AUDIT_EVENTS"]],
    "usernames": ["root"],
    "label_ids": [_gid("Label")],
    "reviewer_usernames": ["root"],
    "escalation_policy_steps": [],
    "rotations": [],
    "participants": [],
    "move_targets": [],
    "actions": [],
    "rules": [],
}

# Common substrings in error messages related to schema issues
SCHEMA_ERROR_PATTERNS = (
    "doesn't exist on type",
    "isn't a defined input type",
    "isn't defined",
    "parse error",
    "parse_error",
    "selections can't be made on scalars",
    "list dimension mismatch",
    "argument type mismatch",
    "variable is declared",
    "variable $",
    "is declared by",
    "but not used",
    "expected type",
    "field '",
    "unknown field",
    "unknown argument",
    "cannot query field",
    "no such field",
)

# Common substrings in error messages related to execution issues
EXECUTION_ERROR_PATTERNS = (
    "not found",
    "does not exist",
    "couldn't find",
    "could not be found",
    "invalid id",
    "invalid value",
    "must exist",
    "must be filled",
    "is not valid",
    "is invalid",
    "you don't have permission",
    "you are not authorized",
    "unauthorized",
    "forbidden",
    "access denied",
    "requires authentication",
    "not allowed",
    "coercion error",
    "argument 'id'",
    "argument 'input'",
    "invalid global id",
    "record not found",
    "provided invalid value",
    "failed to authorize",
    "failed to",
)

SKIP_PARAM_TYPES = {"Dict", "dict"}

SKIP_TOOLS: Dict[str, str] = {
    "design_management_upload": "requires file upload bytes",
    "commit_create": "requires complex actions list",
    "epic_tree_reorder": "requires complex move_parameters",
    "oncall_rotation_create": "requires complex rotation schedule object",
    "oncall_rotation_update": "requires complex rotation schedule object",
    "create_diff_note": "requires complex position object",
    "create_image_diff_note": "requires complex position object",
    "reposition_image_diff_note": "requires complex position object",
    "update_image_diff_note": "requires complex position object",
}

QUERY_TOOLS = {
    "board_list",
    "ci_application_settings",
    "ci_config",
    "ci_minutes_usage",
    "ci_variables",
    "container_repository",
    "current_license",
    "current_user",
    "design_management",
    "devops_adoption_enabled_namespaces",
    "echo",
    "epic_board_list",
    "geo_node",
    "gitpod_enabled",
    "group",
    "instance_security_dashboard",
    "issue",
    "issues",
    "iteration",
    "jobs",
    "license_history_entries",
    "merge_request",
    "metadata",
    "milestone",
    "namespace",
    "package",
    "project",
    "projects",
    "query_complexity",
    "runner",
    "runner_platforms",
    "runner_setup",
    "runners",
    "snippets",
    "subscription_future_entries",
    "timelogs",
    "todo",
    "topics",
    "usage_trends_measurements",
    "user",
    "users",
    "vulnerabilities",
    "vulnerabilities_count_by_day",
    "vulnerability",
    "work_item",
}


class GitLabTest:
    def __init__(self, mcp_server: Any = None) -> None:
        self.mcp_server = mcp_server
        self.results: list[tuple[str, str, str]] = []

    def run(self) -> list[tuple[str, str, str]]:
        token = os.getenv("GRAPHQL_TOKEN")

        self.mcp_server.auth["token"] = token
        tools = self._get_tools()

        queries = sorted(name for name in tools if not self._is_mutation(name))
        mutations = sorted(name for name in tools if self._is_mutation(name))

        print(
            f"Tools  : {len(tools)} total "
            f"({len(queries)} queries, {len(mutations)} mutations)"
        )
        print("─" * 60)

        print(f"\n[QUERIES — {len(queries)}]")
        for name in queries:
            self.try_call(name, tools[name])

        print(f"\n[MUTATIONS — {len(mutations)}]")
        for name in mutations:
            self.try_call(name, tools[name])

        return list(self.results)

    def print_summary(self) -> None:
        """Render a summary matching the existing standalone script output."""
        passed = sum(1 for status, _, _ in self.results if status == "PASS")
        xfailed = sum(1 for status, _, _ in self.results if status == "XFAIL")
        failed = sum(1 for status, _, _ in self.results if status == "FAIL")
        skipped = sum(1 for status, _, _ in self.results if status == "SKIP")
        total = len(self.results)

        print(f"\n{'─' * 60}")
        print(
            f"Results: {passed} passed / {xfailed} xfail (schema ok, bad data)"
            f" / {failed} failed / {skipped} skipped  (total {total})\n"
        )

        if failed:
            print("Schema failures (need fixing in gitlab_server.py):")
            for status, name, msg in self.results:
                if status == "FAIL":
                    print(f"  • {name}: {textwrap.shorten(msg, 100)}")

    def try_call(self, fn_name: str, fn: Any) -> None:
        """Attempt to call a single tool with generated arguments."""
        if fn_name in SKIP_TOOLS:
            self.record("SKIP", fn_name, SKIP_TOOLS[fn_name])
            return

        sig = inspect.signature(fn)
        kwargs: Dict[str, Any] = {}

        for pname, param in sig.parameters.items():
            if param.default is not inspect.Parameter.empty:
                continue

            if pname in FIXTURES:
                kwargs[pname] = FIXTURES[pname]
                continue

            ann = param.annotation
            ann_str = str(ann)
            if any(token in ann_str for token in SKIP_PARAM_TYPES):
                self.record(
                    "SKIP",
                    fn_name,
                    f"no fixture for complex param '{pname}: {ann_str}'",
                )
                return

            kwargs[pname] = self._guess_args(pname, ann)

        try:
            result = fn(**kwargs)
        except Exception as exc:
            self.record("FAIL", fn_name, f"exception: {exc}")
            return

        errors = result.get("errors") if isinstance(result, dict) else None
        if not errors:
            self.record("PASS", fn_name)
            return

        kind = self._classify_errors(errors)
        messages = "; ".join(
            error.get("message", str(error)) for error in errors
        )

        if kind == "schema":
            self.record("FAIL", fn_name, messages)
        elif kind == "execution":
            self.record("XFAIL", fn_name, messages)
        else:
            print(f" Mixed schema/execution errors for {fn_name}: {messages}")
            schema_messages = "; ".join(
                error.get("message", "")
                for error in errors
                if any(
                    pattern in error.get("message", "").lower()
                    for pattern in SCHEMA_ERROR_PATTERNS
                )
            )
            self.record("FAIL", fn_name, schema_messages)

    def record(self, status: str, name: str, detail: str = "") -> None:
        """Store and print a single tool test outcome."""
        suffix = f"  — {textwrap.shorten(detail, 110)}" if detail else ""
        print(f"  {status}  {name}{suffix}")
        self.results.append((status, name, detail))

    def _get_tools(self) -> Dict[str, Any]:
        return {
            name: tool.fn
            for name, tool in self.mcp_server.mcp._tool_manager._tools.items()
            if name != "gitlab_set_token"
        }

    def _classify_errors(self, errors: list[dict[str, Any]]) -> str:
        schema_count = 0
        execution_count = 0
        for error in errors:
            message = error.get("message", "").lower()
            is_schema = any(
                pattern in message for pattern in SCHEMA_ERROR_PATTERNS
            )
            is_execution = any(
                pattern in message for pattern in EXECUTION_ERROR_PATTERNS
            )
            if is_schema:
                schema_count += 1
            elif is_execution:
                execution_count += 1
            else:
                schema_count += 1

        if schema_count and execution_count:
            return "mixed"
        if schema_count:
            return "schema"
        return "execution"

    def _guess_args(self, pname: str, annotation: Any) -> Any:
        name = pname.lower()
        origin = getattr(annotation, "__origin__", None)

        if origin is list:
            args = getattr(annotation, "__args__", [str])
            inner = self._guess_args(pname, args[0]) if args else "item"
            return [inner]

        if annotation is bool:
            return False
        if annotation is float:
            return 0.0
        if annotation is int:
            return 0
        if any(token in name for token in ("_id", "id")):
            return _gid("Unknown")
        if any(token in name for token in ("path", "_path")):
            return PROJECT_PATH
        if "iid" in name:
            return "1"
        if "url" in name:
            return "https://example.com"
        if "date" in name or "time" in name:
            return "2024-01-01T00:00:00Z"
        if "name" in name:
            return "test-name"
        if "title" in name:
            return "Test title"
        if any(token in name for token in ("body", "content", "description")):
            return "test content"
        if "token" in name:
            return "fake-token"
        if any(token in name for token in ("sha", "ref", "branch")):
            return "main"
        if "username" in name:
            return "root"
        if "email" in name:
            return "test@example.com"
        if "emoji" in name:
            return "thumbsup"
        if "tag" in name:
            return "v1.0.0"
        if "note" in name or "summary" in name:
            return "test note"
        if "yaml" in name or "policy" in name:
            return "---\nname: test\n"
        return "test-value"

    def _is_mutation(self, name: str) -> bool:
        return name not in QUERY_TOOLS


if __name__ == "__main__":
    import servers.trulyfinal_gitlab_server as server

    test = GitLabTest(mcp_server=server)
    test.run()
    test.print_summary()
