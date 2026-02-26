"""
GitLab GraphQL MCP Tools
Auto-generated from src/reference/index.md by scripts/extract_graphql_tools_via_gemini.py
Do not edit manually — re-run the script to regenerate.
"""

import os
from typing import Any, Dict, List, Optional

import requests
from fastmcp import FastMCP

mcp = FastMCP("GitLab GraphQL API Server")

BASE_URL = os.getenv("GITLAB_BASE_URL", "http://127.0.0.1:8023").rstrip("/")
DEFAULT_TIMEOUT = float(os.getenv("GITLAB_TIMEOUT", "30"))

auth: Dict[str, Any] = {"token": os.getenv("GRAPHQL_TOKEN")}


def _graphql_request(
    query: str,
    variables: dict | None = None,
    token: str | None = None,
) -> Any:
    """Send a GraphQL request to the GitLab /api/graphql endpoint."""
    tok = token or auth.get("token")
    if not tok:
        raise ValueError(
            "Missing GitLab token. Set GRAPHQL_TOKEN env var or call gitlab_set_token()."
        )
    url = f"{BASE_URL}/api/graphql"
    headers = {
        "Authorization": f"Bearer {tok}",
        "Content-Type": "application/json",
    }
    payload: Dict[str, Any] = {"query": query}
    if variables:
        payload["variables"] = variables
    resp = requests.post(url, headers=headers, json=payload, timeout=DEFAULT_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def gitlab_set_token(token: str) -> str:
    """Set (or replace) the GitLab Bearer token used by every tool in this server."""
    auth["token"] = token
    return "ok"

# ============================================================================
# QUERY TOOLS
# ============================================================================

# --- Query.boardList ---
@mcp.tool()
def board_list(id: str, issue_filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Finds an issue board list by its global ID.

    Args:
        id (str): Global ID of the list.
        issue_filters (Optional[Dict[str, Any]]): Filters applied when getting issue metadata in the board list.
    """
    query = """
        query BoardListQuery($id: ListID!, $issueFilters: BoardIssueInput) {
            boardList(id: $id, issueFilters: $issueFilters) {
                id
                title
                listType
                position
                issues {
                    nodes {
                        id
                        iid
                        title
                        webUrl
                        state
                    }
                    pageInfo {
                        endCursor
                        hasNextPage
                    }
                }
            }
        }
    """
    variables = {"id": id}
    if issue_filters is not None:
        variables["issueFilters"] = issue_filters
    return _graphql_request(query, variables)

# --- Query.ciApplicationSettings ---
@mcp.tool()
def ci_application_settings() -> Dict[str, Any]:
    """
    Retrieve CI related settings that apply to the entire instance.

    Args:
        (none)
    """
    query = """
        query {
            ciApplicationSettings {
                id
                autoDevopsEnabled
                jobLogExpiryDuration
                keepLatestArtifact
                pipelineLimit
                pipelineLimitPerGroup
                allowStaleRunnerCleanup
            }
        }
    """
    return _graphql_request(query)

# --- Query.ciConfig ---
@mcp.tool()
def ci_config(
    content: str,
    project_path: str,
    dry_run: Optional[bool] = None,
    sha: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Lints and processes the contents of a CI config.

    Args:
        content: Contents of `.gitlab-ci.yml`.
        project_path: Project of the CI config.
        dry_run: Run pipeline creation simulation, or only do static check.
        sha: Sha for the pipeline.
    """
    variables: Dict[str, Any] = {
        "content": content,
        "projectPath": project_path,
    }
    query_args = ["$content: String!", "$projectPath: ID!"]
    call_args = ["content: $content", "projectPath: $projectPath"]

    if dry_run is not None:
        variables["dryRun"] = dry_run
        query_args.append("$dryRun: Boolean")
        call_args.append("dryRun: $dryRun")
    if sha is not None:
        variables["sha"] = sha
        query_args.append("$sha: String")
        call_args.append("sha: $sha")

    query = f"""
    query CiConfigQuery({', '.join(query_args)}) {{
        ciConfig({', '.join(call_args)}) {{
            status
            errors
            warnings {{
                content
                type
            }}
            mergedYaml
        }}
    }}
    """
    return _graphql_request(query, variables)

# --- Query.ciMinutesUsage ---
@mcp.tool()
def ci_minutes_usage(namespace_id: str) -> Dict[str, Any]:
    """Retrieve CI/CD minutes usage data for a namespace.

    Args:
        namespace_id: Global ID of the Namespace for the monthly CI/CD minutes usage.
    """
    query = """
        query CiMinutesUsageQuery($namespaceId: NamespaceID!) {
            ciMinutesUsage(namespaceId: $namespaceId) {
                nodes {
                    id
                    month
                    year
                    sharedRunnersDuration
                    sharedRunnersDurationInSeconds
                }
                pageInfo {
                    endCursor
                    hasNextPage
                }
            }
        }
    """
    variables = {"namespaceId": namespace_id}
    return _graphql_request(query, variables)

# --- Query.ciVariables ---
@mcp.tool()
def ci_variables() -> Dict[str, Any]:
    """
    List of the instance's CI/CD variables.
    """
    query = """
        query {
          ciVariables {
            nodes {
              id
              key
              value
              variableType
              environmentScope
            }
            pageInfo {
              endCursor
              hasNextPage
            }
          }
        }
    """
    return _graphql_request(query)

# --- Query.containerRepository ---
@mcp.tool()
def container_repository(id: str) -> Dict[str, Any]:
    """Find a container repository by its global ID.

    Args:
        id (str): Global ID of the container repository.
    """
    query = """
    query ContainerRepositoryDetails($id: ContainerRepositoryID!) {
      containerRepository(id: $id) {
        id
        name
        path
        location
        status
        tagCount
        createdAt
        updatedAt
        expirationPolicy {
          id
          name
          cadence
          keepN
          olderThan
          enabled
        }
      }
    }
    """
    variables = {"id": id}
    return _graphql_request(query, variables)

# --- Query.currentLicense ---
@mcp.tool()
def current_license() -> Dict[str, Any]:
    """Retrieve details about the current license in GitLab.

    Returns:
        Dict[str, Any]: A dictionary containing information about the current license.
    """
    query = """
        query {
            currentLicense {
                id
                activeUsers
                expiresAt
                startsAt
                plan {
                    name
                }
                trial
                usersLimit
                email
                customerName
            }
        }
    """
    return _graphql_request(query)

# --- Query.currentUser ---
@mcp.tool()
def current_user() -> Dict[str, Any]:
    """Get information about the current user."""
    query = """
        query {
            currentUser {
                id
                username
                name
                state
                email
                webUrl
                avatarUrl
                bot
                publicEmail
            }
        }
    """
    return _graphql_request(query)

# --- Query.designManagement ---
@mcp.tool()
def design_management() -> Dict[str, Any]:
    """
    Fetches fields related to design management.

    Args:
        (none)
    """
    query = """
    query {
      designManagement {
        id
        designs {
          nodes {
            id
            filename
            fullPath
            image
          }
          pageInfo {
            endCursor
            hasNextPage
          }
        }
      }
    }
    """
    return _graphql_request(query)

# --- Query.devopsAdoptionEnabledNamespaces ---
@mcp.tool()
def devops_adoption_enabled_namespaces(
    display_namespace_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Get configured DevOps adoption namespaces.

    Args:
        display_namespace_id (Optional[str]): Filter by display namespace.
    """
    query = """
    query DevopsAdoptionEnabledNamespaces($displayNamespaceId: NamespaceID) {
      devopsAdoptionEnabledNamespaces(displayNamespaceId: $displayNamespaceId) {
        nodes {
          id
          displayNamespace {
            id
            name
            fullPath
          }
        }
        pageInfo {
          endCursor
          hasNextPage
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "displayNamespaceId": display_namespace_id,
    }
    return _graphql_request(query, variables)

# --- Query.echo ---
@mcp.tool()
def echo(text: str) -> Dict[str, Any]:
    """
    Tests the API by echoing back the provided text.

    Args:
        text (str): Text to echo back.
    """
    query = """
        query Echo($text: String!) {
            echo(text: $text)
        }
    """
    variables = {"text": text}
    return _graphql_request(query, variables)

# --- Query.epicBoardList ---
@mcp.tool()
def epic_board_list(
    id: str,
    epic_filters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Retrieve a list of epics for an epic board list.

    Args:
        id: Global ID of the list.
        epic_filters: Filters applied when getting epic metadata in the epic board list.
    """
    query = """
        query EpicBoardList($id: BoardsEpicListID!, $epicFilters: EpicFilters) {
            epicBoardList(id: $id, epicFilters: $epicFilters) {
                id
                title
                epics {
                    nodes {
                        id
                        iid
                        title
                        state
                        startDate
                        dueDate
                        webUrl
                        author {
                            username
                            webUrl
                        }
                    }
                    pageInfo {
                        endCursor
                        hasNextPage
                    }
                }
            }
        }
    """
    variables: Dict[str, Any] = {"id": id}
    if epic_filters is not None:
        variables["epicFilters"] = epic_filters

    return _graphql_request(query, variables)

# --- Query.geoNode ---
@mcp.tool()
def geo_node(name: Optional[str] = None) -> Dict[str, Any]:
    """Finds a Geo node.

    Args:
        name (str, optional): Name of the Geo node. Defaults to the current Geo node name.
    """
    query = """
        query GeoNode($name: String) {
            geoNode(name: $name) {
                id
                name
                url
                primary
                enabled
                fileReplicationFactor
                syncStatus {
                    lastEventId
                    lastEventTimestamp
                }
            }
        }
    """
    variables: Dict[str, Any] = {}
    if name is not None:
        variables["name"] = name

    return _graphql_request(query, variables)

# --- Query.gitpodEnabled ---
@mcp.tool()
def gitpod_enabled() -> Dict[str, Any]:
    """Checks if Gitpod is enabled in application settings."""
    query = """
        query {
            gitpodEnabled
        }
    """
    return _graphql_request(query)

# --- Query.group ---
@mcp.tool()
def group(full_path: str) -> Dict[str, Any]:
    """
    Finds a group by its full path.

    Args:
        full_path: Full path of the group. For example, `gitlab-org/gitlab-foss`.
    """
    query = """
        query ($fullPath: ID!) {
            group(fullPath: $fullPath) {
                id
                name
                fullName
                fullPath
                description
                webUrl
                visibility
                createdAt
                updatedAt
                projectsCount
            }
        }
    """
    variables = {"fullPath": full_path}
    return _graphql_request(query, variables)

# --- Query.instanceSecurityDashboard ---
@mcp.tool()
def instance_security_dashboard() -> Dict[str, Any]:
    """Retrieves fields related to the Instance Security Dashboard."""
    query = """
        query {
            instanceSecurityDashboard {
                id
                name
                vulnerabilityReport {
                    vulnerabilitiesCountByDay {
                        date
                        count
                    }
                    # Include a few top-level aggregates or summaries from the report itself
                    criticalVulnerabilitiesCount
                    highVulnerabilitiesCount
                    mediumVulnerabilitiesCount
                    lowVulnerabilitiesCount
                    infoVulnerabilitiesCount
                    unknownVulnerabilitiesCount
                }
                vulnerabilityGrades {
                    grade
                    count
                }
                projects {
                    nodes {
                        id
                        name
                        fullPath
                    }
                    pageInfo {
                        endCursor
                        hasNextPage
                    }
                }
            }
        }
    """
    return _graphql_request(query)

# --- Query.issue ---
@mcp.tool()
def issue(id: str) -> Dict[str, Any]:
    """
    Finds a specific issue by its global ID.

    Args:
        id (str): Global ID of the issue.
    """
    query = """
        query ($id: IssueID!) {
            issue(id: $id) {
                id
                iid
                title
                description
                state
                createdAt
                updatedAt
                webUrl
                author {
                    id
                    username
                }
            }
        }
    """
    variables = {"id": id}
    return _graphql_request(query, variables)

# --- Query.issues ---
@mcp.tool()
def issues(
    assignee_id: Optional[str] = None,
    assignee_username: Optional[str] = None,
    assignee_usernames: Optional[List[str]] = None,
    author_username: Optional[str] = None,
    closed_after: Optional[str] = None,
    closed_before: Optional[str] = None,
    confidential: Optional[bool] = None,
    created_after: Optional[str] = None,
    created_before: Optional[str] = None,
    crm_contact_id: Optional[str] = None,
    crm_organization_id: Optional[str] = None,
    epic_id: Optional[str] = None,
    health_status_filter: Optional[str] = None,
    iid: Optional[str] = None,
    iids: Optional[List[str]] = None,
    in_fields: Optional[List[str]] = None,
    include_subepics: Optional[bool] = None,
    iteration_id: Optional[List[str]] = None,
    iteration_wildcard_id: Optional[str] = None,
    label_name: Optional[List[str]] = None,
    milestone_title: Optional[List[str]] = None,
    milestone_wildcard_id: Optional[str] = None,
    my_reaction_emoji: Optional[str] = None,
    not_filter: Optional[Dict[str, Any]] = None,
    or_filter: Optional[Dict[str, Any]] = None,
    search: Optional[str] = None,
    sort: Optional[str] = None,
    state: Optional[str] = None,
    types: Optional[List[str]] = None,
    updated_after: Optional[str] = None,
    updated_before: Optional[str] = None,
    weight: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Retrieves issues visible by the current user.

    Args:
        assignee_id (Optional[str]): ID of a user assigned to the issues. Wildcard values "NONE" and "ANY" are supported.
        assignee_username (Optional[str]): Deprecated: Use `assignee_usernames`.
        assignee_usernames (Optional[List[str]]): Usernames of users assigned to the issue.
        author_username (Optional[str]): Username of the author of the issue.
        closed_after (Optional[str]): Issues closed after this date (ISO 8601 format).
        closed_before (Optional[str]): Issues closed before this date (ISO 8601 format).
        confidential (Optional[bool]): Filter for confidential issues. If "false", excludes confidential issues. If "true", returns only confidential issues.
        created_after (Optional[str]): Issues created after this date (ISO 8601 format).
        created_before (Optional[str]): Issues created before this date (ISO 8601 format).
        crm_contact_id (Optional[str]): ID of a contact assigned to the issues.
        crm_organization_id (Optional[str]): ID of an organization assigned to the issues.
        epic_id (Optional[str]): ID of an epic associated with the issues, "none" and "any" values are supported.
        health_status_filter (Optional[str]): Health status of the issue, "none" and "any" values are supported (e.g., "ON_TRACK", "AT_RISK").
        iid (Optional[str]): IID of the issue. For example, "1".
        iids (Optional[List[str]]): List of IIDs of issues. For example, `["1", "2"]`.
        in_fields (Optional[List[str]]): Specify the fields to perform the search in. Defaults to `[TITLE, DESCRIPTION]`. Requires the `search` argument.
        include_subepics (Optional[bool]): Whether to include subepics when filtering issues by epicId.
        iteration_id (Optional[List[str]]): List of iteration Global IDs applied to the issue.
        iteration_wildcard_id (Optional[str]): Filter by iteration ID wildcard (e.g., "CURRENT", "NONE").
        label_name (Optional[List[str]]): Labels applied to this issue.
        milestone_title (Optional[List[str]]): Milestone applied to this issue.
        milestone_wildcard_id (Optional[str]): Filter issues by milestone ID wildcard (e.g., "CURRENT", "NONE").
        my_reaction_emoji (Optional[str]): Filter by reaction emoji applied by the current user. Wildcard values "NONE" and "ANY" are supported.
        not_filter (Optional[Dict[str, Any]]): Negated arguments, e.g., `{"labelName": ["bug"]}`.
        or_filter (Optional[Dict[str, Any]]): List of arguments with inclusive OR, e.g., `{"labelName": ["bug"], "milestoneTitle": ["1.0"]}`.
        search (Optional[str]): Search query for title or description.
        sort (Optional[str]): Sort issues by this criteria (e.g., "CREATED_ASC", "UPDATED_DESC").
        state (Optional[str]): Current state of this issue. Valid values: "opened", "closed", "locked", "all".
        types (Optional[List[str]]): Filter issues by the given issue types (e.g., ["ISSUE", "INCIDENT"]).
        updated_after (Optional[str]): Issues updated after this date (ISO 8601 format).
        updated_before (Optional[str]): Issues updated before this date (ISO 8601 format).
        weight (Optional[str]): Weight applied to the issue, "none" and "any" values are supported.
    """
    query_args = {}
    variables = {}
    arg_definitions = []

    def add_arg(name: str, value: Any, graphql_type: str, python_name: str = None):
        if value is not None:
            if python_name is None:
                python_name = name
            var_name = f"var_{name}"
            query_args[name] = f"${var_name}"
            variables[var_name] = value
            arg_definitions.append(f"${var_name}: {graphql_type}")

    add_arg("assigneeId", assignee_id, "String")
    add_arg("assigneeUsername", assignee_username, "String")
    add_arg("assigneeUsernames", assignee_usernames, "[String!]")
    add_arg("authorUsername", author_username, "String")
    add_arg("closedAfter", closed_after, "Time")
    add_arg("closedBefore", closed_before, "Time")
    add_arg("confidential", confidential, "Boolean")
    add_arg("createdAfter", created_after, "Time")
    add_arg("createdBefore", created_before, "Time")
    add_arg("crmContactId", crm_contact_id, "String")
    add_arg("crmOrganizationId", crm_organization_id, "String")
    add_arg("epicId", epic_id, "String")
    add_arg("healthStatusFilter", health_status_filter, "HealthStatusFilter")
    add_arg("iid", iid, "String")
    add_arg("iids", iids, "[String!]")
    add_arg("in", in_fields, "[IssuableSearchableField!]", python_name="in_fields")
    add_arg("includeSubepics", include_subepics, "Boolean")
    add_arg("iterationId", iteration_id, "[ID]")
    add_arg("iterationWildcardId", iteration_wildcard_id, "IterationWildcardId")
    add_arg("labelName", label_name, "[String]")
    add_arg("milestoneTitle", milestone_title, "[String]")
    add_arg("milestoneWildcardId", milestone_wildcard_id, "MilestoneWildcardId")
    add_arg("myReactionEmoji", my_reaction_emoji, "String")
    add_arg("not", not_filter, "NegatedIssueFilterInput", python_name="not_filter")
    add_arg("or", or_filter, "UnionedIssueFilterInput", python_name="or_filter")
    add_arg("search", search, "String")
    add_arg("sort", sort, "IssueSort")
    add_arg("state", state, "IssuableState")
    add_arg("types", types, "[IssueType!]")
    add_arg("updatedAfter", updated_after, "Time")
    add_arg("updatedBefore", updated_before, "Time")
    add_arg("weight", weight, "String")

    args_str = ", ".join([f"{k}: {v}" for k, v in query_args.items()])
    arg_definitions_str = f"({', '.join(arg_definitions)})" if arg_definitions else ""

    query = f"""
        query {arg_definitions_str} {{
            issues({args_str}) {{
                nodes {{
                    id
                    iid
                    title
                    state
                    webUrl
                    createdAt
                    updatedAt
                    confidential
                    author {{
                        username
                    }}
                    assignees {{
                        nodes {{
                            username
                        }}
                    }}
                    labels {{
                        nodes {{
                            title
                        }}
                    }}
                    milestone {{
                        title
                    }}
                }}
                pageInfo {{
                    endCursor
                    hasNextPage
                }}
            }}
        }}
    """
    return _graphql_request(query, variables)

# --- Query.iteration ---
@mcp.tool()
def iteration(id: str) -> Dict[str, Any]:
    """
    Finds a GitLab iteration by its ID.

    Args:
        id: The global ID of the iteration to find.
    """
    query = """
        query GetIteration($id: IterationID!) {
            iteration(id: $id) {
                id
                iid
                title
                description
                startDate
                dueDate
                state
                webUrl
                createdAt
                updatedAt
            }
        }
    """
    variables = {"id": id}
    return _graphql_request(query, variables)

# --- Query.jobs ---
@mcp.tool()
def jobs(
    statuses: Optional[List[List[str]]] = None
) -> Dict[str, Any]:
    """
    Retrieves all jobs on this GitLab instance, optionally filtered by status.

    Args:
        statuses: Filter jobs by status. Each inner list represents an OR condition,
                  while statuses within an inner list are AND conditions.
                  Example: `[["SUCCESS", "FAILED"], ["RUNNING"]]`
                  (i.e., (SUCCESS AND FAILED) OR RUNNING).
    """
    query = """
    query Jobs($statuses: [[CiJobStatus!]]) {
      jobs(statuses: $statuses) {
        nodes {
          id
          name
          status
          stage {
            id
            name
          }
          createdAt
          startedAt
          finishedAt
          duration
          allowFailure
          detailedStatus {
            group
            label
            text
            tooltip
            icon
            detailsPath
          }
        }
        pageInfo {
          endCursor
          hasNextPage
          startCursor
          hasPreviousPage
        }
      }
    }
    """
    variables: Dict[str, Any] = {}
    if statuses is not None:
        variables["statuses"] = statuses

    return _graphql_request(query, variables)

# --- Query.licenseHistoryEntries ---
@mcp.tool()
def license_history_entries() -> Dict[str, Any]:
    """Retrieves entries in the license history.

    This tool fetches a list of license history entries, including
    details about each entry, associated user, and license.
    """
    query = """
        query {
            licenseHistoryEntries {
                nodes {
                    id
                    createdAt
                    expiresAt
                    startsAt
                    user {
                        id
                        username
                    }
                    license {
                        id
                        name
                    }
                }
                pageInfo {
                    endCursor
                    hasNextPage
                }
            }
        }
    """
    return _graphql_request(query)

# --- Query.mergeRequest ---
@mcp.tool()
def merge_request(id: str) -> Dict[str, Any]:
    """
    Finds a merge request by its global ID.

    Args:
        id (str): Global ID of the merge request.
    """
    query = """
        query ($id: MergeRequestID!) {
            mergeRequest(id: $id) {
                id
                iid
                title
                state
                webUrl
                createdAt
                updatedAt
                author {
                    username
                    webUrl
                }
                project {
                    fullPath
                }
            }
        }
    """
    variables = {"id": id}
    return _graphql_request(query, variables)

# --- Query.metadata ---
@mcp.tool()
def metadata() -> Dict[str, Any]:
    """Get metadata about GitLab.
    """
    query = """
    query {
        metadata {
            version
            revision
            kasInfo {
                enabled
                url
                version
            }
            userCalloutsPath
            userSettingsPath
        }
    }
    """
    return _graphql_request(query)

# --- Query.milestone ---
@mcp.tool()
def milestone(id: str) -> Dict[str, Any]:
    """Find a milestone by its ID.

    Args:
        id (str): Find a milestone by its ID.
    """
    query = """
    query Milestone($id: MilestoneID!) {
      milestone(id: $id) {
        id
        title
        description
        state
        dueDate
        startDate
        webUrl
        createdAt
        updatedAt
      }
    }
    """
    variables = {"id": id}
    return _graphql_request(query, variables)

# --- Query.namespace ---
@mcp.tool()
def namespace(full_path: str) -> Dict[str, Any]:
    """Finds a GitLab namespace by its full path.

    Args:
        full_path (str): Full path of the project, group, or namespace. For example, `gitlab-org/gitlab-foss`.
    """
    query = f"""
    query {{
      namespace(fullPath: "{full_path}") {{
        id
        fullPath
        name
        description
        webUrl
        visibility
        avatarUrl
      }}
    }}
    """
    return _graphql_request(query)

# --- Query.package ---
@mcp.tool()
def package(id: str) -> Dict[str, Any]:
    """
    Finds a specific package by its global ID.

    Args:
        id (str): Global ID of the package.
    """
    query = f"""
    query {{
      package(id: "{id}") {{
        id
        name
        version
        packageType
        status
        createdAt
        updatedAt
        project {{
          id
          name
          fullPath
        }}
      }}
    }}
    """
    return _graphql_request(query)

# --- Query.project ---
@mcp.tool()
def project(full_path: str) -> Dict[str, Any]:
    """
    Find a project by its full path.

    Args:
        full_path: Full path of the project, group, or namespace. For example, `gitlab-org/gitlab-foss`.
    """
    query = f"""
    query {{
      project(fullPath: "{full_path}") {{
        id
        name
        fullPath
        description
        webUrl
        createdAt
        updatedAt
        visibility
        archived
        starCount
      }}
    }}
    """
    return _graphql_request(query)

# --- Query.projects ---
@mcp.tool()
def projects(
    ids: Optional[List[str]] = None,
    membership: Optional[bool] = None,
    search: Optional[str] = None,
    search_namespaces: Optional[bool] = None,
    sort: Optional[str] = None,
    topics: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Find projects visible to the current user.

    Args:
        ids: Filter projects by IDs.
        membership: Return only projects that the current user is a member of.
        search: Search query for project name, path, or description.
        search_namespaces: Include namespace in project search.
        sort: Sort order of results, e.g., 'id_desc' or 'name_asc'.
        topics: Filter projects by topics.
    """
    query_args_list = []
    variables = {}

    if ids is not None:
        query_args_list.append("ids: $ids")
        variables["ids"] = ids
    if membership is not None:
        query_args_list.append("membership: $membership")
        variables["membership"] = membership
    if search is not None:
        query_args_list.append("search: $search")
        variables["search"] = search
    if search_namespaces is not None:
        query_args_list.append("searchNamespaces: $searchNamespaces")
        variables["searchNamespaces"] = search_namespaces
    if sort is not None:
        query_args_list.append("sort: $sort")
        variables["sort"] = sort
    if topics is not None:
        query_args_list.append("topics: $topics")
        variables["topics"] = topics

    args_string = ", ".join(query_args_list)
    if args_string:
        args_string = f"({args_string})"

    query = f"""
    query {{
      projects{args_string} {{
        nodes {{
          id
          name
          fullPath
          description
          webUrl
          visibility
          createdAt
          topics
        }}
        pageInfo {{
          endCursor
          hasNextPage
          hasPreviousPage
          startCursor
        }}
      }}
    }}
    """
    return _graphql_request(query, variables)

# --- Query.queryComplexity ---
@mcp.tool()
def query_complexity() -> Dict[str, Any]:
    """
    Get information about the complexity of the GraphQL query.
    """
    query = """
        query {
            queryComplexity {
                score
                limit
                remaining
                maxComplexity
            }
        }
    """
    return _graphql_request(query)

# --- Query.runner ---
@mcp.tool()
def runner(id: str) -> Dict[str, Any]:
    """Find a specific GitLab CI runner by ID.

    Args:
        id: The ID of the CI runner to find.
    """
    query = f"""
query {{
    runner(id: "{id}") {{
        id
        description
        name
        status
        ipAddress
        version
        contactedAt
        tagList
        locked
        maximumTimeout
        accessLevel
        ownerProject {{
            id
            fullPath
        }}
    }}
}}
"""
    return _graphql_request(query)

# --- Query.runnerPlatforms ---
@mcp.tool()
def runner_platforms() -> Dict[str, Any]:
    """Retrieves supported runner platforms.

    Args:
        (none)
    """
    query = """
    query {
        runnerPlatforms {
            nodes {
                id
                name
                architecture
                os
            }
            pageInfo {
                endCursor
                hasNextPage
            }
        }
    }
    """
    return _graphql_request(query)

# --- Query.runnerSetup ---
@mcp.tool()
def runner_setup(
    architecture: str,
    platform: str,
    group_id: Optional[str] = None,
    project_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Retrieves runner setup instructions for a given architecture and platform.

    Args:
        architecture: Architecture to generate the instructions for.
        platform: Platform to generate the instructions for.
        group_id: Deprecated in 13.11. No longer used.
        project_id: Deprecated in 13.11. No longer used.
    """
    query = """
    query RunnerSetupQuery(
      $architecture: String!
      $platform: String!
      $groupId: GroupID
      $projectId: ProjectID
    ) {
      runnerSetup(
        architecture: $architecture
        platform: $platform
        groupId: $groupId
        projectId: $projectId
      ) {
        commands
        installUrl
        shell
        token
        name
      }
    }
    """
    variables: Dict[str, Any] = {
        "architecture": architecture,
        "platform": platform,
    }
    if group_id is not None:
        variables["groupId"] = group_id
    if project_id is not None:
        variables["projectId"] = project_id

    return _graphql_request(query, variables)

# --- Query.runners ---
@mcp.tool()
def runners(
    paused: Optional[bool] = None,
    search: Optional[str] = None,
    sort: Optional[str] = None,
    status: Optional[str] = None,
    tag_list: Optional[List[List[str]]] = None,
    type: Optional[str] = None,
    upgrade_status: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Find runners visible to the current user.

    Args:
        paused: Filter runners by `paused` (true) or `active` (false) status.
        search: Filter by full token or partial text in description field.
        sort: Sort order of results (e.g., 'CREATED_ASC', 'CONTACTED_AT_DESC').
        status: Filter runners by status (e.g., 'ONLINE', 'OFFLINE', 'NOT_CONNECTED').
        tag_list: Filter by tags associated with the runner (e.g., [['linux'], ['docker', 'build']]).
        type: Filter runners by type (e.g., 'INSTANCE_TYPE', 'GROUP_TYPE', 'PROJECT_TYPE').
        upgrade_status: Filter by upgrade status (e.g., 'AVAILABLE', 'RECOMMENDED', 'NOT_APPLICABLE').
    """
    query_args = []
    variables = {}
    variable_definitions = []

    if paused is not None:
        query_args.append("paused: $paused")
        variables["paused"] = paused
        variable_definitions.append("$paused: Boolean")
    if search is not None:
        query_args.append("search: $search")
        variables["search"] = search
        variable_definitions.append("$search: String")
    if sort is not None:
        query_args.append("sort: $sort")
        variables["sort"] = sort
        variable_definitions.append("$sort: CiRunnerSort")
    if status is not None:
        query_args.append("status: $status")
        variables["status"] = status
        variable_definitions.append("$status: CiRunnerStatus")
    if tag_list is not None:
        query_args.append("tagList: $tagList")
        variables["tagList"] = tag_list
        variable_definitions.append("$tagList: [[String!]]")
    if type is not None:
        # Use 'runnerType' as the GraphQL variable name to avoid collision with Python 'type' keyword
        # and potential GraphQL 'type' keyword ambiguities in variable definitions.
        query_args.append("type: $runnerType")
        variables["runnerType"] = type
        variable_definitions.append("$runnerType: CiRunnerType")
    if upgrade_status is not None:
        query_args.append("upgradeStatus: $upgradeStatus")
        variables["upgradeStatus"] = upgrade_status
        variable_definitions.append("$upgradeStatus: CiRunnerUpgradeStatus")

    variables_str = f"({', '.join(variable_definitions)})" if variable_definitions else ""
    args_str = f"({', '.join(query_args)})" if query_args else ""

    query = f"""
query Runners{variables_str} {{
  runners{args_str} {{
    nodes {{
      id
      description
      paused
      status
      runnerType
      version
      online
      contactedAt
      createdAt
      tagList
    }}
    pageInfo {{
      endCursor
      hasNextPage
    }}
  }}
}}
    """
    return _graphql_request(query, variables)

# --- Query.snippets ---
@mcp.tool()
def snippets(
    author_id: Optional[str] = None,
    explore: Optional[bool] = None,
    ids: Optional[List[str]] = None,
    project_id: Optional[str] = None,
    type: Optional[str] = None,
    visibility: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Finds snippets visible to the current user, with optional filtering.

    Args:
        author_id: ID of an author.
        explore: Explore personal snippets.
        ids: Array of global snippet IDs.
        project_id: ID of a project.
        type: Type of snippet (e.g., 'ProjectSnippet', 'PersonalSnippet').
        visibility: Visibility of the snippet (e.g., 'PUBLIC', 'INTERNAL', 'PRIVATE').
    """
    query_args = []
    variables = {}

    if author_id is not None:
        query_args.append("authorId: $authorId")
        variables["authorId"] = author_id
    if explore is not None:
        query_args.append("explore: $explore")
        variables["explore"] = explore
    if ids is not None:
        query_args.append("ids: $ids")
        variables["ids"] = ids
    if project_id is not None:
        query_args.append("projectId: $projectId")
        variables["projectId"] = project_id
    if type is not None:
        query_args.append("type: $type")
        variables["type"] = type
    if visibility is not None:
        query_args.append("visibility: $visibility")
        variables["visibility"] = visibility

    args_string = ", ".join(query_args)
    
    # query = f"""
    #     query Snippets({", ".join(f"${k}: {v.__class__.__name__}" for k, v in variables.items() if k != "ids" or v is None else "$ids: [SnippetID!]")} ) {{
    #         snippets({args_string}) {{
    #             nodes {{
    #                 id
    #                 title
    #                 descriptionHtml
    #                 visibility
    #                 createdAt
    #                 updatedAt
    #                 fileName
    #                 webUrl
    #                 author {{
    #                     id
    #                     username
    #                     name
    #                 }}
    #                 project {{
    #                     id
    #                     fullPath
    #                     name
    #                 }}
    #             }}
    #             pageInfo {{
    #                 endCursor
    #                 hasNextPage
    #             }}
    #         }}
    #     }}
    # """
    
    # GraphQL variable types need to be correct, especially for lists and enums
    # The current variable mapping is simpler than trying to guess the exact GraphQL type.
    # The GraphQL client typically handles serialization for basic types, but for complex
    # types like enums or custom IDs, string representation is usually expected.
    # For `ids` which is `[SnippetID!]`, the variable definition should be `ids: [SnippetID!]`.
    
    # Refined variable type definitions for the query string
    variable_definitions = []
    if author_id is not None:
        variable_definitions.append("$authorId: UserID")
    if explore is not None:
        variable_definitions.append("$explore: Boolean")
    if ids is not None:
        variable_definitions.append("$ids: [SnippetID!]")
    if project_id is not None:
        variable_definitions.append("$projectId: ProjectID")
    if type is not None:
        variable_definitions.append("$type: TypeEnum") # Assuming TypeEnum as per API
    if visibility is not None:
        variable_definitions.append("$visibility: VisibilityScopesEnum") # Assuming VisibilityScopesEnum

    variable_definition_string = ", ".join(variable_definitions)
    
    query = f"""
        query Snippets({variable_definition_string}) {{
            snippets({args_string}) {{
                nodes {{
                    id
                    title
                    descriptionHtml
                    visibility
                    createdAt
                    updatedAt
                    fileName
                    webUrl
                    author {{
                        id
                        username
                        name
                    }}
                    project {{
                        id
                        fullPath
                        name
                    }}
                }}
                pageInfo {{
                    endCursor
                    hasNextPage
                }}
            }}
        }}
    """

    return _graphql_request(query, variables)

# --- Query.subscriptionFutureEntries ---
@mcp.tool()
def subscription_future_entries() -> Dict[str, Any]:
    """Retrieves fields related to entries in future subscriptions.

    Returns:
        Dict[str, Any]: The GraphQL response data.
    """
    query = """
        query {
            subscriptionFutureEntries {
                nodes {
                    id
                    productName
                    quantity
                    startDate
                    endDate
                    __typename
                }
                pageInfo {
                    endCursor
                    hasNextPage
                }
            }
        }
    """
    return _graphql_request(query)

# --- Query.timelogs ---
@mcp.tool()
def timelogs(
    endDate: Optional[str] = None,
    endTime: Optional[str] = None,
    groupId: Optional[str] = None,
    projectId: Optional[str] = None,
    startDate: Optional[str] = None,
    startTime: Optional[str] = None,
    username: Optional[str] = None,
) -> Dict[str, Any]:
    """Find timelogs visible to the current user.

    Args:
        endDate: List timelogs within a date range where the logged date is equal to or before endDate.
        endTime: List timelogs within a time range where the logged time is equal to or before endTime.
        groupId: List timelogs for a group.
        projectId: List timelogs for a project.
        startDate: List timelogs within a date range where the logged date is equal to or after startDate.
        startTime: List timelogs within a time range where the logged time is equal to or after startTime.
        username: List timelogs for a user.
    """
    variables: Dict[str, Any] = {}
    query_args: List[str] = []

    if endDate is not None:
        query_args.append("endDate: $endDate")
        variables["endDate"] = endDate
    if endTime is not None:
        query_args.append("endTime: $endTime")
        variables["endTime"] = endTime
    if groupId is not None:
        query_args.append("groupId: $groupId")
        variables["groupId"] = groupId
    if projectId is not None:
        query_args.append("projectId: $projectId")
        variables["projectId"] = projectId
    if startDate is not None:
        query_args.append("startDate: $startDate")
        variables["startDate"] = startDate
    if startTime is not None:
        query_args.append("startTime: $startTime")
        variables["startTime"] = startTime
    if username is not None:
        query_args.append("username: $username")
        variables["username"] = username

    query_args_str = ", ".join(query_args)
    if query_args_str:
        query_args_str = f"({query_args_str})"

    query = f"""
query TimelogsQuery(
  $endDate: Time,
  $endTime: Time,
  $groupId: GroupID,
  $projectId: ProjectID,
  $startDate: Time,
  $startTime: Time,
  $username: String
) {{
  timelogs{query_args_str} {{
    nodes {{
      id
      spentAt
      timeSpent
      summary
      user {{
        username
      }}
      issue {{
        iid
        title
        webUrl
      }}
      mergeRequest {{
        iid
        title
        webUrl
      }}
    }}
    pageInfo {{
      endCursor
      hasNextPage
      startCursor
      hasPreviousPage
    }}
  }}
}}
"""
    return _graphql_request(query, variables)

# --- Query.todo ---
@mcp.tool()
def todo(id: str) -> Dict[str, Any]:
    """
    Retrieve a single to-do item.

    Args:
        id (str): ID of the to-do item.
    """
    query = """
        query GetTodoItem($id: TodoID!) {
            todo(id: $id) {
                id
                state
                action
                body
                targetType
                createdAt
                dueDate
                project {
                    id
                    name
                    fullPath
                }
                group {
                    id
                    name
                    fullPath
                }
                author {
                    id
                    username
                    name
                }
            }
        }
    """
    variables = {"id": id}
    return _graphql_request(query, variables)

# --- Query.topics ---
@mcp.tool()
def topics(search: Optional[str] = None) -> Dict[str, Any]:
    """
    Find project topics.

    Args:
        search (Optional[str]): Search query for topic name.
    """
    query = """
    query Topics($search: String) {
      topics(search: $search) {
        nodes {
          id
          name
          description
          title
        }
        pageInfo {
          endCursor
          hasNextPage
        }
      }
    }
    """
    variables = {}
    if search is not None:
        variables["search"] = search

    return _graphql_request(query, variables)

# --- Query.usageTrendsMeasurements ---
@mcp.tool()
def usage_trends_measurements(
    identifier: str,
    recorded_after: Optional[str] = None,
    recorded_before: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Get statistics on the instance's usage trends.

    Args:
        identifier (str): Type of measurement or statistics to retrieve (e.g., "PROJECTS_CREATED").
        recorded_after (Optional[str]): Measurement recorded after this date (ISO 8601 format).
        recorded_before (Optional[str]): Measurement recorded before this date (ISO 8601 format).
    """
    query = """
        query UsageTrendsMeasurements(
            $identifier: MeasurementIdentifier!
            $recordedAfter: Time
            $recordedBefore: Time
        ) {
            usageTrendsMeasurements(
                identifier: $identifier
                recordedAfter: $recordedAfter
                recordedBefore: $recordedBefore
            ) {
                nodes {
                    id
                    identifier
                    recordedAt
                    value
                }
                pageInfo {
                    endCursor
                    hasNextPage
                    startCursor
                    hasPreviousPage
                }
            }
        }
    """
    variables: Dict[str, Any] = {
        "identifier": identifier,
    }
    if recorded_after is not None:
        variables["recordedAfter"] = recorded_after
    if recorded_before is not None:
        variables["recordedBefore"] = recorded_before

    return _graphql_request(query, variables)

# --- Query.user ---
@mcp.tool()
def user(id: Optional[str] = None, username: Optional[str] = None) -> Dict[str, Any]:
    """Find a user by ID or username.

    Args:
        id: ID of the User.
        username: Username of the User.
    """
    query_args = []
    variables = {}
    graphql_variables_def = []

    if id is not None:
        query_args.append("id: $id")
        variables["id"] = id
        graphql_variables_def.append("$id: UserID")

    if username is not None:
        query_args.append("username: $username")
        variables["username"] = username
        graphql_variables_def.append("$username: String")

    args_string = ", ".join(query_args)
    variables_def_string = f"({', '.join(graphql_variables_def)})" if graphql_variables_def else ""

    query = f"""
        query {variables_def_string} {{
            user({args_string}) {{
                id
                username
                name
                state
                webUrl
                avatarUrl
                email
                createdAt
                bio
            }}
        }}
    """
    return _graphql_request(query, variables)

# --- Query.users ---
@mcp.tool()
def users(
    admins: Optional[bool] = None,
    ids: Optional[List[str]] = None,
    search: Optional[str] = None,
    sort: Optional[str] = None,
    usernames: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Find users in GitLab.

    Args:
        admins (Optional[bool]): Return only admin users.
        ids (Optional[List[str]]): List of user Global IDs.
        search (Optional[str]): Query to search users by name, username, or primary email.
        sort (Optional[str]): Sort users by this criteria.
        usernames (Optional[List[str]]): List of usernames.
    """
    query_args = []
    variables = {}

    if admins is not None:
        query_args.append("admins: $admins")
        variables["admins"] = admins
    if ids is not None:
        query_args.append("ids: $ids")
        variables["ids"] = ids
    if search is not None:
        query_args.append("search: $search")
        variables["search"] = search
    if sort is not None:
        query_args.append("sort: $sort")
        variables["sort"] = sort
    if usernames is not None:
        query_args.append("usernames: $usernames")
        variables["usernames"] = usernames

    args_string = ", ".join(query_args)
    if args_string:
        args_string = f"({args_string})"

    # Define the GraphQL variable definitions for the query
    variable_definitions = []
    if admins is not None:
        variable_definitions.append("$admins: Boolean")
    if ids is not None:
        variable_definitions.append("$ids: [ID!]")
    if search is not None:
        variable_definitions.append("$search: String")
    if sort is not None:
        variable_definitions.append("$sort: Sort")
    if usernames is not None:
        variable_definitions.append("$usernames: [String!]")

    vars_definition_string = ""
    if variable_definitions:
        vars_definition_string = f"({', '.join(variable_definitions)})"

    query = f"""
        query getUsers{vars_definition_string} {{
            users{args_string} {{
                nodes {{
                    id
                    username
                    name
                    state
                    webUrl
                    avatarUrl
                    email
                    createdAt
                }}
                pageInfo {{
                    endCursor
                    hasNextPage
                }}
            }}
        }}
    """
    return _graphql_request(query, variables)

# --- Query.vulnerabilities ---
@mcp.tool()
def vulnerabilities(
    cluster_agent_id: Optional[List[str]] = None,
    cluster_id: Optional[List[str]] = None,
    has_issues: Optional[bool] = None,
    has_resolution: Optional[bool] = None,
    image: Optional[List[str]] = None,
    project_id: Optional[List[str]] = None,
    report_type: Optional[List[str]] = None,
    scanner: Optional[List[str]] = None,
    scanner_id: Optional[List[str]] = None,
    severity: Optional[List[str]] = None,
    sort: Optional[str] = None,
    state: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Retrieves vulnerabilities reported on projects on the current user's instance security dashboard.

    Args:
        cluster_agent_id (Optional[List[str]]): Filter vulnerabilities by cluster agent ID.
        cluster_id (Optional[List[str]]): Filter vulnerabilities by cluster ID.
        has_issues (Optional[bool]): Returns only vulnerabilities which have linked issues.
        has_resolution (Optional[bool]): Returns only vulnerabilities which have been resolved on default branch.
        image (Optional[List[str]]): Filter vulnerabilities by location image.
        project_id (Optional[List[str]]): Filter vulnerabilities by project ID.
        report_type (Optional[List[str]]): Filter vulnerabilities by report type.
        scanner (Optional[List[str]]): Filter vulnerabilities by VulnerabilityScanner.externalId.
        scanner_id (Optional[List[str]]): Filter vulnerabilities by scanner ID.
        severity (Optional[List[str]]): Filter vulnerabilities by severity.
        sort (Optional[str]): List vulnerabilities by sort order.
        state (Optional[List[str]]): Filter vulnerabilities by state.
    """
    query_args = []
    variables = {}
    variable_definitions = []

    if cluster_agent_id is not None:
        query_args.append("clusterAgentId: $clusterAgentId")
        variables["clusterAgentId"] = cluster_agent_id
        variable_definitions.append("$clusterAgentId: [ClustersAgentID!]")
    if cluster_id is not None:
        query_args.append("clusterId: $clusterId")
        variables["clusterId"] = cluster_id
        variable_definitions.append("$clusterId: [ClustersClusterID!]")
    if has_issues is not None:
        query_args.append("hasIssues: $hasIssues")
        variables["hasIssues"] = has_issues
        variable_definitions.append("$hasIssues: Boolean")
    if has_resolution is not None:
        query_args.append("hasResolution: $hasResolution")
        variables["hasResolution"] = has_resolution
        variable_definitions.append("$hasResolution: Boolean")
    if image is not None:
        query_args.append("image: $image")
        variables["image"] = image
        variable_definitions.append("$image: [String!]")
    if project_id is not None:
        query_args.append("projectId: $projectId")
        variables["projectId"] = project_id
        variable_definitions.append("$projectId: [ID!]")
    if report_type is not None:
        query_args.append("reportType: $reportType")
        variables["reportType"] = report_type
        variable_definitions.append("$reportType: [VulnerabilityReportType!]")
    if scanner is not None:
        query_args.append("scanner: $scanner")
        variables["scanner"] = scanner
        variable_definitions.append("$scanner: [String!]")
    if scanner_id is not None:
        query_args.append("scannerId: $scannerId")
        variables["scannerId"] = scanner_id
        variable_definitions.append("$scannerId: [VulnerabilitiesScannerID!]")
    if severity is not None:
        query_args.append("severity: $severity")
        variables["severity"] = severity
        variable_definitions.append("$severity: [VulnerabilitySeverity!]")
    if sort is not None:
        query_args.append("sort: $sort")
        variables["sort"] = sort
        variable_definitions.append("$sort: VulnerabilitySort")
    if state is not None:
        query_args.append("state: $state")
        variables["state"] = state
        variable_definitions.append("$state: [VulnerabilityState!]")

    args_string = ", ".join(query_args)
    variable_definitions_string = (f"({', '.join(variable_definitions)})" if variable_definitions else "")

    query = f"""
    query {variable_definitions_string} {{
        vulnerabilities({args_string}) {{
            nodes {{
                id
                title
                description
                severity
                state
                reportType
                vulnerabilityPath
                createdAt
                updatedAt
                location {{
                    image
                }}
                scanner {{
                    id
                    name
                }}
            }}
            pageInfo {{
                endCursor
                hasNextPage
            }}
        }}
    }}
    """
    return _graphql_request(query, variables)

# --- Query.vulnerabilitiesCountByDay ---
@mcp.tool()
def vulnerabilities_count_by_day(start_date: str, end_date: str) -> Dict[str, Any]:
    """
    Fetches the historical number of vulnerabilities per day for the instance security dashboard.

    Args:
        start_date (str): First day for which to fetch vulnerability history (ISO8601Date).
        end_date (str): Last day for which to fetch vulnerability history (ISO8601Date).
    """
    query = """
    query VulnerabilitiesCountByDay($startDate: ISO8601Date!, $endDate: ISO8601Date!) {
      vulnerabilitiesCountByDay(startDate: $startDate, endDate: $endDate) {
        nodes {
          date
          count
        }
        pageInfo {
          endCursor
          hasNextPage
          hasPreviousPage
          startCursor
        }
        count
      }
    }
    """
    variables = {
        "startDate": start_date,
        "endDate": end_date,
    }
    return _graphql_request(query, variables)

# --- Query.vulnerability ---
@mcp.tool()
def vulnerability(id: str) -> Dict[str, Any]:
    """
    Finds a vulnerability by its global ID.

    Args:
        id (str): Global ID of the Vulnerability.
    """
    query = """
    query VulnerabilityQuery($id: VulnerabilityID!) {
      vulnerability(id: $id) {
        id
        title
        description
        severity
        state
        reportType
        createdAt
        updatedAt
        project {
          id
          name
          fullPath
        }
        scanner {
          id
          name
        }
      }
    }
    """
    variables = {"id": id}
    return _graphql_request(query, variables)

# --- Query.workItem ---
@mcp.tool()
def work_item(id: str) -> Dict[str, Any]:
    """
    Finds a specific work item by its global ID.

    Args:
        id (str): Global ID of the work item.
    """
    query = """
    query WorkItem($id: WorkItemID!) {
      workItem(id: $id) {
        id
        title
        description
        state
        confidential
        createdAt
        updatedAt
        workItemType {
          name
        }
      }
    }
    """
    variables = {"id": id}
    return _graphql_request(query, variables)



# ============================================================================
# MUTATION
# ============================================================================

# --- Mutation.addProjectToSecurityDashboard ---
@mcp.tool()
def add_project_to_security_dashboard(
    id: str, client_mutation_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Adds a project to the Instance Security Dashboard.

    Args:
        id: ID of the project to be added to Instance Security Dashboard.
        client_mutation_id: A unique identifier for the client performing the mutation.
    """
    query = """
        mutation AddProjectToSecurityDashboard($id: ProjectID!, $clientMutationId: String) {
          addProjectToSecurityDashboard(input: { id: $id, clientMutationId: $clientMutationId }) {
            clientMutationId
            errors
            project {
              id
              name
              fullPath
              visibility
            }
          }
        }
    """
    variables = {
        "id": id,
        "clientMutationId": client_mutation_id,
    }
    return _graphql_request(query, variables)

# --- Mutation.adminSidekiqQueuesDeleteJobs ---
@mcp.tool()
def admin_sidekiq_queues_delete_jobs(
    queue_name: str,
    artifact_size: Optional[str] = None,
    artifact_used_cdn: Optional[str] = None,
    artifacts_dependencies_count: Optional[str] = None,
    artifacts_dependencies_size: Optional[str] = None,
    caller_id: Optional[str] = None,
    client_id: Optional[str] = None,
    client_mutation_id: Optional[str] = None,
    feature_category: Optional[str] = None,
    job_id: Optional[str] = None,
    pipeline_id: Optional[str] = None,
    project: Optional[str] = None,
    related_class: Optional[str] = None,
    remote_ip: Optional[str] = None,
    root_caller_id: Optional[str] = None,
    root_namespace: Optional[str] = None,
    subscription_plan: Optional[str] = None,
    user: Optional[str] = None,
    user_id: Optional[str] = None,
    worker_class: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Deletes jobs from a Sidekiq queue based on specified criteria.

    Args:
        queue_name: Name of the queue to delete jobs from.
        artifact_size: Delete jobs matching artifact_size in the context metadata.
        artifact_used_cdn: Delete jobs matching artifact_used_cdn in the context metadata.
        artifacts_dependencies_count: Delete jobs matching artifacts_dependencies_count in the context metadata.
        artifacts_dependencies_size: Delete jobs matching artifacts_dependencies_size in the context metadata.
        caller_id: Delete jobs matching caller_id in the context metadata.
        client_id: Delete jobs matching client_id in the context metadata.
        client_mutation_id: A unique identifier for the client performing the mutation.
        feature_category: Delete jobs matching feature_category in the context metadata.
        job_id: Delete jobs matching job_id in the context metadata.
        pipeline_id: Delete jobs matching pipeline_id in the context metadata.
        project: Delete jobs matching project in the context metadata.
        related_class: Delete jobs matching related_class in the context metadata.
        remote_ip: Delete jobs matching remote_ip in the context metadata.
        root_caller_id: Delete jobs matching root_caller_id in the context metadata.
        root_namespace: Delete jobs matching root_namespace in the context metadata.
        subscription_plan: Delete jobs matching subscription_plan in the context metadata.
        user: Delete jobs matching user in the context metadata.
        user_id: Delete jobs matching user_id in the context metadata.
        worker_class: Delete jobs with the given worker class.
    """
    query = """
    mutation AdminSidekiqQueuesDeleteJobs(
      $artifactSize: String,
      $artifactUsedCdn: String,
      $artifactsDependenciesCount: String,
      $artifactsDependenciesSize: String,
      $callerId: String,
      $clientId: String,
      $clientMutationId: String,
      $featureCategory: String,
      $jobId: String,
      $pipelineId: String,
      $project: String,
      $queueName: String!,
      $relatedClass: String,
      $remoteIp: String,
      $rootCallerId: String,
      $rootNamespace: String,
      $subscriptionPlan: String,
      $user: String,
      $userId: String,
      $workerClass: String
    ) {
      adminSidekiqQueuesDeleteJobs(input: {
        artifactSize: $artifactSize,
        artifactUsedCdn: $artifactUsedCdn,
        artifactsDependenciesCount: $artifactsDependenciesCount,
        artifactsDependenciesSize: $artifactsDependenciesSize,
        callerId: $callerId,
        clientId: $clientId,
        clientMutationId: $clientMutationId,
        featureCategory: $featureCategory,
        jobId: $jobId,
        pipelineId: $pipelineId,
        project: $project,
        queueName: $queueName,
        relatedClass: $relatedClass,
        remoteIp: $remoteIp,
        rootCallerId: $rootCallerId,
        rootNamespace: $rootNamespace,
        subscriptionPlan: $subscriptionPlan,
        user: $user,
        userId: $userId,
        workerClass: $workerClass
      }) {
        clientMutationId
        errors
        result {
          message
          success
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "queueName": queue_name,
        "artifactSize": artifact_size,
        "artifactUsedCdn": artifact_used_cdn,
        "artifactsDependenciesCount": artifacts_dependencies_count,
        "artifactsDependenciesSize": artifacts_dependencies_size,
        "callerId": caller_id,
        "clientId": client_id,
        "clientMutationId": client_mutation_id,
        "featureCategory": feature_category,
        "jobId": job_id,
        "pipelineId": pipeline_id,
        "project": project,
        "relatedClass": related_class,
        "remoteIp": remote_ip,
        "rootCallerId": root_caller_id,
        "rootNamespace": root_namespace,
        "subscriptionPlan": subscription_plan,
        "user": user,
        "userId": user_id,
        "workerClass": worker_class,
    }
    # Filter out None values from variables to avoid sending null for optional fields
    variables = {k: v for k, v in variables.items() if v is not None}

    return _graphql_request(query, variables)

# --- Mutation.alertSetAssignees ---
@mcp.tool()
def alert_set_assignees(
    assignee_usernames: List[str],
    iid: str,
    project_path: str,
    client_mutation_id: Optional[str] = None,
    operation_mode: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Sets assignees for an alert management alert.

    Args:
        assignee_usernames: Usernames to assign to the alert. Replaces existing assignees by default.
        iid: IID of the alert to mutate.
        project_path: Project the alert to mutate is in.
        client_mutation_id: A unique identifier for the client performing the mutation.
        operation_mode: Operation to perform. Defaults to REPLACE.
    """
    variables: Dict[str, Any] = {
        "assigneeUsernames": assignee_usernames,
        "iid": iid,
        "projectPath": project_path,
    }

    # Prepare GraphQL variable definitions for the mutation header
    var_defs: List[str] = [
        "$assigneeUsernames: [String!]!",
        "$iid: String!",
        "$projectPath: ID!",
    ]

    # Prepare input arguments for the mutation body
    input_args: List[str] = [
        "assigneeUsernames: $assigneeUsernames",
        "iid: $iid",
        "projectPath: $projectPath",
    ]

    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id
        var_defs.append("$clientMutationId: String")
        input_args.append("clientMutationId: $clientMutationId")

    if operation_mode is not None:
        variables["operationMode"] = operation_mode
        var_defs.append("$operationMode: MutationOperationMode")
        input_args.append("operationMode: $operationMode")

    var_defs_str = ", ".join(var_defs)
    input_args_str = ", ".join(input_args)

    query = f"""
    mutation AlertSetAssigneesMutation({var_defs_str}) {{
      alertSetAssignees(input: {{ {input_args_str} }}) {{
        alert {{
          id
          iid
          title
          status
          assignees {{
            nodes {{
              username
              id
            }}
          }}
        }}
        clientMutationId
        errors
        issue {{
          id
          iid
          title
        }}
        todo {{
          id
          state
        }}
      }}
    }}
    """
    return _graphql_request(query, variables)

# --- Mutation.alertTodoCreate ---
@mcp.tool()
def alert_todo_create(
    iid: str,
    project_path: str,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Creates a to-do item for a given alert.

    Args:
        iid (str): IID of the alert to mutate.
        project_path (str): Project the alert to mutate is in.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation AlertTodoCreate($iid: String!, $projectPath: ID!, $clientMutationId: String) {
      alertTodoCreate(input: {
        iid: $iid,
        projectPath: $projectPath,
        clientMutationId: $clientMutationId
      }) {
        alert {
          iid
          title
          status
        }
        clientMutationId
        errors
        issue {
          iid
          title
          webUrl
        }
        todo {
          id
          state
          body
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "iid": iid,
        "projectPath": project_path,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.apiFuzzingCiConfigurationCreate ---
@mcp.tool()
def api_fuzzing_ci_configuration_create(
    api_specification_file: str,
    project_path: str,
    scan_mode: str,
    target: str,
    auth_password: Optional[str] = None,
    auth_username: Optional[str] = None,
    client_mutation_id: Optional[str] = None,
    scan_profile: Optional[str] = None,
) -> Dict[str, Any]:
    """Create an API Fuzzing CI configuration.

    Args:
        api_specification_file (str): File path or URL to the file that defines the API surface for scanning.
        project_path (str): Full path of the project.
        scan_mode (str): Mode for API fuzzing scans.
        target (str): URL for the target of API fuzzing scans.
        auth_password (Optional[str]): CI variable containing the password for authenticating with the target API.
        auth_username (Optional[str]): CI variable containing the username for authenticating with the target API.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        scan_profile (Optional[str]): Name of a default profile to use for scanning. Ex: Quick-10.
    """

    graphql_variables_declaration = []
    graphql_input_fields = []
    variables: Dict[str, Any] = {}

    # Required fields
    graphql_variables_declaration.append("$apiSpecificationFile: String!")
    graphql_input_fields.append("apiSpecificationFile: $apiSpecificationFile")
    variables["apiSpecificationFile"] = api_specification_file

    graphql_variables_declaration.append("$projectPath: ID!")
    graphql_input_fields.append("projectPath: $projectPath")
    variables["projectPath"] = project_path

    graphql_variables_declaration.append("$scanMode: ApiFuzzingScanMode!")
    graphql_input_fields.append("scanMode: $scanMode")
    variables["scanMode"] = scan_mode

    graphql_variables_declaration.append("$target: String!")
    graphql_input_fields.append("target: $target")
    variables["target"] = target

    # Optional fields
    if auth_password is not None:
        graphql_variables_declaration.append("$authPassword: String")
        graphql_input_fields.append("authPassword: $authPassword")
        variables["authPassword"] = auth_password
    if auth_username is not None:
        graphql_variables_declaration.append("$authUsername: String")
        graphql_input_fields.append("authUsername: $authUsername")
        variables["authUsername"] = auth_username
    if client_mutation_id is not None:
        graphql_variables_declaration.append("$clientMutationId: String")
        graphql_input_fields.append("clientMutationId: $clientMutationId")
        variables["clientMutationId"] = client_mutation_id
    if scan_profile is not None:
        graphql_variables_declaration.append("$scanProfile: String")
        graphql_input_fields.append("scanProfile: $scanProfile")
        variables["scanProfile"] = scan_profile

    graphql_variables_str = ",\n    ".join(graphql_variables_declaration)
    graphql_input_str = ",\n        ".join(graphql_input_fields)

    query = f"""
mutation ApiFuzzingCiConfigurationCreate(
    {graphql_variables_str}
) {{
    apiFuzzingCiConfigurationCreate(input: {{
        {graphql_input_str}
    }}) {{
        clientMutationId
        configurationYaml
        errors
        gitlabCiYamlEditPath
    }}
}}
"""
    return _graphql_request(query, variables)

# --- Mutation.artifactDestroy ---
@mcp.tool()
def artifact_destroy(
    id: str,
    client_mutation_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Destroys a CI job artifact.

    Args:
        id: ID of the artifact to delete.
        client_mutation_id: A unique identifier for the client performing the mutation.
    """
    query = """
        mutation artifactDestroyMutation($id: CiJobArtifactID!, $clientMutationId: String) {
            artifactDestroy(input: { id: $id, clientMutationId: $clientMutationId }) {
                artifact {
                    id
                    name
                    path
                    size
                    fileType
                }
                clientMutationId
                errors
            }
        }
    """
    variables: Dict[str, Any] = {
        "id": id,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables=variables)

# --- Mutation.auditEventsStreamingDestinationEventsAdd ---
@mcp.tool()
def audit_events_streaming_destination_events_add(
    destination_id: str,
    event_type_filters: List[List[str]],
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Adds event type filters to an audit events streaming destination.

    Args:
        destination_id (str): Destination id.
        event_type_filters (List[List[str]]): List of event type filters to add for streaming.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation AuditEventsStreamingDestinationEventsAdd(
      $destinationId: AuditEventsExternalAuditEventDestinationID!,
      $eventTypeFilters: [[String!]!]!,
      $clientMutationId: String
    ) {
      auditEventsStreamingDestinationEventsAdd(input: {
        destinationId: $destinationId,
        eventTypeFilters: $eventTypeFilters,
        clientMutationId: $clientMutationId
      }) {
        clientMutationId
        errors
        eventTypeFilters
      }
    }
    """
    variables: Dict[str, Any] = {
        "destinationId": destination_id,
        "eventTypeFilters": event_type_filters,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.auditEventsStreamingDestinationEventsRemove ---
@mcp.tool()
def audit_events_streaming_destination_events_remove(
    destination_id: str,
    event_type_filters: List[List[str]],
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Removes event type filters from an audit events streaming destination.

    Args:
        destination_id (str): Destination URL ID.
        event_type_filters (List[List[str]]): List of event type filters to remove from streaming.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation AuditEventsStreamingDestinationEventsRemove(
      $clientMutationId: String,
      $destinationId: AuditEventsExternalAuditEventDestinationID!,
      $eventTypeFilters: [[String!]!]!
    ) {
      auditEventsStreamingDestinationEventsRemove(input: {
        clientMutationId: $clientMutationId,
        destinationId: $destinationId,
        eventTypeFilters: $eventTypeFilters
      }) {
        clientMutationId
        errors
      }
    }
    """
    variables: Dict[str, Any] = {
        "destinationId": destination_id,
        "eventTypeFilters": event_type_filters,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.auditEventsStreamingHeadersCreate ---
@mcp.tool()
def audit_events_streaming_headers_create(
    destination_id: str,
    key: str,
    value: str,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Creates a streaming audit event header for a given destination.

    Args:
        destination_id: ID of the destination to associate the header with.
        key: The header key.
        value: The header value.
        client_mutation_id: A unique identifier for the client performing the mutation.
    """
    query = """
    mutation AuditEventsStreamingHeadersCreate(
      $clientMutationId: String
      $destinationId: AuditEventsExternalAuditEventDestinationID!
      $key: String!
      $value: String!
    ) {
      auditEventsStreamingHeadersCreate(input: {
        clientMutationId: $clientMutationId
        destinationId: $destinationId
        key: $key
        value: $value
      }) {
        clientMutationId
        errors
        header {
          id
          key
          value
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "destinationId": destination_id,
        "key": key,
        "value": value,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.auditEventsStreamingHeadersDestroy ---
@mcp.tool()
def audit_events_streaming_headers_destroy(
    header_id: str,
    client_mutation_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Deletes an audit event streaming header.

    Args:
        header_id (str): Header to delete.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation AuditEventsStreamingHeadersDestroy($input: AuditEventsStreamingHeadersDestroyInput!) {
      auditEventsStreamingHeadersDestroy(input: $input) {
        clientMutationId
        errors
      }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "headerId": header_id
        }
    }
    if client_mutation_id:
        variables["input"]["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.auditEventsStreamingHeadersUpdate ---
@mcp.tool()
def audit_events_streaming_headers_update(
    header_id: str,
    key: str,
    value: str,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Updates an existing audit events streaming header.

    Args:
        header_id (str): Header to update.
        key (str): Header key.
        value (str): Header value.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation AuditEventsStreamingHeadersUpdate(
      $clientMutationId: String,
      $headerId: AuditEventsStreamingHeaderID!,
      $key: String!,
      $value: String!
    ) {
      auditEventsStreamingHeadersUpdate(input: {
        clientMutationId: $clientMutationId,
        headerId: $headerId,
        key: $key,
        value: $value
      }) {
        clientMutationId
        errors
        header {
          id
          key
          value
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "headerId": header_id,
        "key": key,
        "value": value,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.awardEmojiAdd ---
@mcp.tool()
def award_emoji_add(
    awardable_id: str,
    name: str,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Adds an emoji award to a resource.

    Args:
        awardable_id (str): Global ID of the awardable resource.
        name (str): Emoji name.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation AwardEmojiAddMutation($awardableId: AwardableID!, $name: String!, $clientMutationId: String) {
      awardEmojiAdd(input: {
        awardableId: $awardableId,
        name: $name,
        clientMutationId: $clientMutationId
      }) {
        awardEmoji {
          id
          name
          awardable {
            id
          }
        }
        clientMutationId
        errors
      }
    }
    """
    variables: Dict[str, Any] = {
        "awardableId": awardable_id,
        "name": name,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.awardEmojiRemove ---
@mcp.tool()
def award_emoji_remove(
    awardable_id: str,
    name: str,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Removes an award emoji from an awardable resource.

    Args:
        awardable_id: Global ID of the awardable resource.
        name: Emoji name.
        client_mutation_id: A unique identifier for the client performing the mutation.
    """
    query = """
    mutation AwardEmojiRemove($awardableId: AwardableID!, $name: String!, $clientMutationId: String) {
        awardEmojiRemove(input: {
            awardableId: $awardableId,
            name: $name,
            clientMutationId: $clientMutationId
        }) {
            awardEmoji {
                id
                name
                awardable {
                    id
                }
                user {
                    id
                    username
                    name
                }
            }
            clientMutationId
            errors
        }
    }
    """
    variables: Dict[str, Any] = {
        "awardableId": awardable_id,
        "name": name,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.awardEmojiToggle ---
@mcp.tool()
def award_emoji_toggle(
    awardable_id: str,
    name: str,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Toggles (awards or removes) an emoji on an awardable resource.

    Args:
        awardable_id: Global ID of the awardable resource.
        name: Emoji name.
        client_mutation_id: A unique identifier for the client performing the mutation.
    """
    query = """
    mutation awardEmojiToggle($awardableId: AwardableID!, $name: String!, $clientMutationId: String) {
      awardEmojiToggle(input: {
        awardableId: $awardableId,
        name: $name,
        clientMutationId: $clientMutationId
      }) {
        awardEmoji {
          id
          name
          awardable {
            id
          }
          user {
            id
            username
          }
        }
        clientMutationId
        errors
        toggledOn
      }
    }
    """
    variables: Dict[str, Any] = {
        "awardableId": awardable_id,
        "name": name,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.boardEpicCreate ---
@mcp.tool()
def board_epic_create(
    board_id: str,
    group_path: str,
    list_id: str,
    title: str,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Creates an epic on a GitLab board.

    Args:
        board_id (str): Global ID of the board that the epic is in.
        group_path (str): Group the epic to create is in.
        list_id (str): Global ID of the epic board list in which epic will be created.
        title (str): Title of the epic.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation boardEpicCreate($input: BoardEpicCreateInput!) {
      boardEpicCreate(input: $input) {
        clientMutationId
        epic {
          id
          iid
          title
          description
          state
          createdAt
          updatedAt
          group {
            id
            fullPath
          }
        }
        errors
      }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "boardId": board_id,
            "groupPath": group_path,
            "listId": list_id,
            "title": title,
        }
    }
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.boardListCreate ---
@mcp.tool()
def board_list_create(
    board_id: str,
    assignee_id: Optional[str] = None,
    backlog: Optional[bool] = None,
    client_mutation_id: Optional[str] = None,
    iteration_id: Optional[str] = None,
    label_id: Optional[str] = None,
    milestone_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Creates a new list on an issue board.

    Args:
        board_id: Global ID of the issue board to mutate.
        assignee_id: Global ID of an existing user to associate with the list.
        backlog: Set to true to create the backlog list.
        client_mutation_id: A unique identifier for the client performing the mutation.
        iteration_id: Global ID of an existing iteration to associate with the list.
        label_id: Global ID of an existing label to associate with the list.
        milestone_id: Global ID of an existing milestone to associate with the list.
    """
    query = """
        mutation boardListCreate(
            $assigneeId: UserID,
            $backlog: Boolean,
            $boardId: BoardID!,
            $clientMutationId: String,
            $iterationId: IterationID,
            $labelId: LabelID,
            $milestoneId: MilestoneID
        ) {
            boardListCreate(input: {
                assigneeId: $assigneeId,
                backlog: $backlog,
                boardId: $boardId,
                clientMutationId: $clientMutationId,
                iterationId: $iterationId,
                labelId: $labelId,
                milestoneId: $milestoneId
            }) {
                clientMutationId
                errors
                list {
                    id
                    title
                    listType
                    position
                    collapsed
                }
            }
        }
    """
    variables: Dict[str, Any] = {
        "assigneeId": assignee_id,
        "backlog": backlog,
        "boardId": board_id,
        "clientMutationId": client_mutation_id,
        "iterationId": iteration_id,
        "labelId": label_id,
        "milestoneId": milestone_id,
    }
    return _graphql_request(query, variables)

# --- Mutation.boardListUpdateLimitMetrics ---
@mcp.tool()
def board_list_update_limit_metrics(
    list_id: str,
    client_mutation_id: Optional[str] = None,
    limit_metric: Optional[str] = None,
    max_issue_count: Optional[int] = None,
    max_issue_weight: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Updates the limit metrics for a board list.

    Args:
        list_id: Global ID of the list.
        client_mutation_id: A unique identifier for the client performing the mutation.
        limit_metric: New limit metric type for the list.
        max_issue_count: New maximum issue count limit.
        max_issue_weight: New maximum issue weight limit.
    """
    query = """
    mutation BoardListUpdateLimitMetrics(
      $clientMutationId: String,
      $limitMetric: ListLimitMetric,
      $listId: ListID!,
      $maxIssueCount: Int,
      $maxIssueWeight: Int
    ) {
      boardListUpdateLimitMetrics(input: {
        clientMutationId: $clientMutationId,
        limitMetric: $limitMetric,
        listId: $listId,
        maxIssueCount: $maxIssueCount,
        maxIssueWeight: $maxIssueWeight
      }) {
        clientMutationId
        errors
        list {
          id
          title
          listType
          position
          maxIssueCount
          maxIssueWeight
          limitMetric
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "listId": list_id,
        "clientMutationId": client_mutation_id,
        "limitMetric": limit_metric,
        "maxIssueCount": max_issue_count,
        "maxIssueWeight": max_issue_weight,
    }
    return _graphql_request(query, variables)

# --- Mutation.bulkEnableDevopsAdoptionNamespaces ---
@mcp.tool()
def bulk_enable_devops_adoption_namespaces(
    namespace_ids: List[str],
    client_mutation_id: Optional[str] = None,
    display_namespace_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Enables DevOps adoption for a list of namespaces.

    Args:
        namespace_ids: List of Namespace IDs to enable DevOps adoption for.
        client_mutation_id: A unique identifier for the client performing the mutation.
        display_namespace_id: Display namespace ID.
    """
    query = """
    mutation BulkEnableDevopsAdoptionNamespaces($input: BulkEnableDevopsAdoptionNamespacesInput!) {
      bulkEnableDevopsAdoptionNamespaces(input: $input) {
        clientMutationId
        enabledNamespaces {
          id
          namespace {
            id
            fullPath
            name
          }
        }
        errors
      }
    }
    """
    variables = {
        "input": {
            "namespaceIds": namespace_ids,
        }
    }
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id
    if display_namespace_id is not None:
        variables["input"]["displayNamespaceId"] = display_namespace_id

    return _graphql_request(query, variables)

# --- Mutation.bulkRunnerDelete ---
@mcp.tool()
def bulk_runner_delete(ids: List[str], client_mutation_id: Optional[str] = None) -> Dict[str, Any]:
    """Delete multiple GitLab CI/CD runners by their IDs.

    Args:
        ids: IDs of the runners to delete.
        client_mutation_id: A unique identifier for the client performing the mutation.
    """
    query = """
    mutation bulkRunnerDelete($ids: [CiRunnerID!]!, $clientMutationId: String) {
      bulkRunnerDelete(input: {
        ids: $ids,
        clientMutationId: $clientMutationId
      }) {
        clientMutationId
        deletedCount
        deletedIds
        errors
      }
    }
    """
    variables = {
        "ids": ids,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.ciCdSettingsUpdate ---
@mcp.tool()
def ci_cd_settings_update(
    full_path: str,
    inbound_job_token_scope_enabled: Optional[bool] = None,
    job_token_scope_enabled: Optional[bool] = None,
    keep_latest_artifact: Optional[bool] = None,
    merge_pipelines_enabled: Optional[bool] = None,
    merge_trains_enabled: Optional[bool] = None,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Updates the CI/CD settings for a project.

    Args:
        full_path: Full Path of the project the settings belong to.
        inbound_job_token_scope_enabled: Indicates CI/CD job tokens generated in other projects have restricted access to this project.
        job_token_scope_enabled: Indicates CI/CD job tokens generated in this project have restricted access to other projects.
        keep_latest_artifact: Indicates if the latest artifact should be kept for this project.
        merge_pipelines_enabled: Indicates if merge pipelines are enabled for the project.
        merge_trains_enabled: Indicates if merge trains are enabled for the project.
        client_mutation_id: A unique identifier for the client performing the mutation.
    """
    query = """
    mutation CiCdSettingsUpdate($input: CiCdSettingsUpdateInput!) {
      ciCdSettingsUpdate(input: $input) {
        ciCdSettings {
          id
          fullPath
          inboundJobTokenScopeEnabled
          jobTokenScopeEnabled
          keepLatestArtifact
          mergePipelinesEnabled
          mergeTrainsEnabled
        }
        clientMutationId
        errors
      }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "fullPath": full_path,
        }
    }
    if inbound_job_token_scope_enabled is not None:
        variables["input"]["inboundJobTokenScopeEnabled"] = inbound_job_token_scope_enabled
    if job_token_scope_enabled is not None:
        variables["input"]["jobTokenScopeEnabled"] = job_token_scope_enabled
    if keep_latest_artifact is not None:
        variables["input"]["keepLatestArtifact"] = keep_latest_artifact
    if merge_pipelines_enabled is not None:
        variables["input"]["mergePipelinesEnabled"] = merge_pipelines_enabled
    if merge_trains_enabled is not None:
        variables["input"]["mergeTrainsEnabled"] = merge_trains_enabled
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables=variables)

# --- Mutation.ciJobTokenScopeAddProject ---
@mcp.tool()
def ci_job_token_scope_add_project(
    project_path: str,
    target_project_path: str,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Add a project to the CI job token scope.

    Args:
        project_path (str): Project that the CI job token scope belongs to.
        target_project_path (str): Project to be added to the CI job token scope.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation CiJobTokenScopeAddProject(
        $projectPath: ID!
        $targetProjectPath: ID!
        $clientMutationId: String
    ) {
        ciJobTokenScopeAddProject(input: {
            projectPath: $projectPath
            targetProjectPath: $targetProjectPath
            clientMutationId: $clientMutationId
        }) {
            ciJobTokenScope {
                id
                allowedProjects {
                    nodes {
                        id
                        fullPath
                        name
                    }
                    pageInfo {
                        endCursor
                        hasNextPage
                    }
                }
            }
            clientMutationId
            errors
        }
    }
    """
    variables = {
        "projectPath": project_path,
        "targetProjectPath": target_project_path,
        "clientMutationId": client_mutation_id,
    }
    return _graphql_request(query, variables)

# --- Mutation.ciJobTokenScopeRemoveProject ---
@mcp.tool()
def ci_job_token_scope_remove_project(
    project_path: str,
    target_project_path: str,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Removes a project from a CI job token's scope of access.

    Args:
        project_path: Project that the CI job token scope belongs to.
        target_project_path: Project to be removed from the CI job token scope.
        client_mutation_id: A unique identifier for the client performing the mutation.
    """
    query = """
    mutation CiJobTokenScopeRemoveProject($input: CiJobTokenScopeRemoveProjectInput!) {
      ciJobTokenScopeRemoveProject(input: $input) {
        ciJobTokenScope {
          id
          project {
            id
            fullPath
          }
          outboundAllowlist {
            nodes {
              id
              fullPath
            }
            pageInfo {
              endCursor
              hasNextPage
            }
          }
        }
        clientMutationId
        errors
      }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "projectPath": project_path,
            "targetProjectPath": target_project_path,
        }
    }
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.clusterAgentDelete ---
@mcp.tool()
def cluster_agent_delete(
    id: str,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Deletes a GitLab cluster agent.

    Args:
        id (str): Global ID of the cluster agent that will be deleted.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation ClusterAgentDelete($input: ClusterAgentDeleteInput!) {
      clusterAgentDelete(input: $input) {
        clientMutationId
        errors
      }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "id": id,
        }
    }
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.clusterAgentTokenCreate ---
@mcp.tool()
def cluster_agent_token_create(
    cluster_agent_id: str,
    name: str,
    client_mutation_id: Optional[str] = None,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Creates a new token for a GitLab Cluster Agent.

    Args:
        cluster_agent_id (str): Global ID of the cluster agent.
        name (str): Name of the token.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        description (Optional[str]): Description of the token.
    """
    query = """
    mutation ClusterAgentTokenCreate($input: ClusterAgentTokenCreateInput!) {
      clusterAgentTokenCreate(input: $input) {
        clientMutationId
        errors
        secret
        token {
          id
          name
          description
          createdAt
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "clusterAgentId": cluster_agent_id,
            "name": name,
        }
    }
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id
    if description is not None:
        variables["input"]["description"] = description

    return _graphql_request(query, variables)

# --- Mutation.clusterAgentTokenRevoke ---
@mcp.tool()
def cluster_agent_token_revoke(
    id: str,
    client_mutation_id: Optional[str] = None
) -> Dict[str, Any]:
    """Revokes a GitLab Cluster Agent Token.

    Args:
        id: Global ID of the agent token that will be revoked.
        client_mutation_id: A unique identifier for the client performing the mutation.
    """
    query = """
    mutation ClusterAgentTokenRevoke($id: ClustersAgentTokenID!, $clientMutationId: String) {
      clusterAgentTokenRevoke(input: { id: $id, clientMutationId: $clientMutationId }) {
        clientMutationId
        errors
      }
    }
    """
    variables = {
        "id": id,
        "clientMutationId": client_mutation_id,
    }
    return _graphql_request(query, variables)

# --- Mutation.commitCreate ---
@mcp.tool()
def commit_create(
    actions: List[Dict[str, Any]],
    branch: str,
    message: str,
    project_path: str,
    client_mutation_id: Optional[str] = None,
    start_branch: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Creates a new commit in a project branch.

    Args:
        actions: Array of action hashes to commit as a batch.
        branch: Name of the branch to commit into, it can be a new branch.
        message: Raw commit message.
        project_path: Project full path the branch is associated with.
        client_mutation_id: A unique identifier for the client performing the mutation.
        start_branch: If on a new branch, name of the original branch.
    """
    query = """
    mutation CommitCreate($input: CommitCreateInput!) {
        commitCreate(input: $input) {
            clientMutationId
            commit {
                id
                sha
                webUrl
            }
            commitPipelinePath
            content
            errors
        }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "actions": actions,
            "branch": branch,
            "message": message,
            "projectPath": project_path,
        }
    }
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id
    if start_branch is not None:
        variables["input"]["startBranch"] = start_branch

    return _graphql_request(query, variables)

# --- Mutation.configureContainerScanning ---
@mcp.tool()
def configure_container_scanning(
    project_path: str,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Configures Container Scanning for a project by creating/modifying a CI/CD file.

    Args:
        project_path: Full path of the project.
        client_mutation_id: A unique identifier for the client performing the mutation.
    """
    query = """
    mutation ConfigureContainerScanning($projectPath: ID!, $clientMutationId: String) {
      configureContainerScanning(input: {
        projectPath: $projectPath,
        clientMutationId: $clientMutationId
      }) {
        branch
        clientMutationId
        errors
        successPath
      }
    }
    """
    variables: Dict[str, Any] = {
        "projectPath": project_path,
        "clientMutationId": client_mutation_id,
    }
    return _graphql_request(query, variables=variables)

# --- Mutation.configureDependencyScanning ---
@mcp.tool()
def configure_dependency_scanning(
    project_path: str,
    client_mutation_id: Optional[str] = None
) -> Dict[str, Any]:
    """Configure Dependency Scanning for a project.

    Args:
        project_path: Full path of the project.
        client_mutation_id: A unique identifier for the client performing the mutation.
    """
    query = """
    mutation ConfigureDependencyScanning($projectPath: ID!, $clientMutationId: String) {
      configureDependencyScanning(input: {
        projectPath: $projectPath,
        clientMutationId: $clientMutationId
      }) {
        branch
        clientMutationId
        errors
        successPath
      }
    }
    """
    variables: Dict[str, Any] = {
        "projectPath": project_path,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.configureSast ---
@mcp.tool()
def configure_sast(
    project_path: str,
    configuration: Dict[str, Any],
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Configure SAST for a project.

    Args:
        project_path (str): Full path of the project.
        configuration (Dict[str, Any]): SAST CI configuration for the project.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation configureSast($input: ConfigureSastInput!) {
      configureSast(input: $input) {
        branch
        clientMutationId
        errors
        successPath
      }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "projectPath": project_path,
            "configuration": configuration,
        }
    }
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.configureSastIac ---
@mcp.tool()
def configure_sast_iac(
    project_path: str,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Enable SAST IaC for a project in a new or modified `.gitlab-ci.yml` file.

    Args:
        project_path (str): Full path of the project.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation configureSastIac($projectPath: ID!, $clientMutationId: String) {
      configureSastIac(input: { projectPath: $projectPath, clientMutationId: $clientMutationId }) {
        branch
        clientMutationId
        errors
        successPath
      }
    }
    """
    variables: Dict[str, Any] = {
        "projectPath": project_path,
        "clientMutationId": client_mutation_id,
    }
    return _graphql_request(query, variables)

# --- Mutation.configureSecretDetection ---
@mcp.tool()
def configure_secret_detection(
    project_path: str, client_mutation_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Configure Secret Detection for a project.

    Args:
        project_path: Full path of the project.
        client_mutation_id: A unique identifier for the client performing the mutation.
    """
    query = """
        mutation ConfigureSecretDetection($projectPath: ID!, $clientMutationId: String) {
            configureSecretDetection(input: {
                projectPath: $projectPath,
                clientMutationId: $clientMutationId
            }) {
                branch
                clientMutationId
                errors
                successPath
            }
        }
    """
    variables: Dict[str, Any] = {
        "projectPath": project_path,
        "clientMutationId": client_mutation_id,
    }
    # Remove None values from variables dictionary
    variables = {k: v for k, v in variables.items() if v is not None}

    return _graphql_request(query, variables)

# --- Mutation.corpusCreate ---
@mcp.tool()
def corpus_create(
    full_path: str,
    package_id: str,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Creates a new corpus for a project.

    Args:
        full_path (str): Project the corpus belongs to.
        package_id (str): ID of the corpus package.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation CorpusCreate($fullPath: ID!, $packageId: PackagesPackageID!, $clientMutationId: String) {
      corpusCreate(input: {
        clientMutationId: $clientMutationId,
        fullPath: $fullPath,
        packageId: $packageId
      }) {
        clientMutationId
        errors
      }
    }
    """
    variables: Dict[str, Any] = {
        "fullPath": full_path,
        "packageId": package_id,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id
    
    return _graphql_request(query, variables)

# --- Mutation.createAlertIssue ---
@mcp.tool()
def create_alert_issue(
    iid: str,
    project_path: str,
    client_mutation_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Creates an issue from an alert management alert.

    Args:
        iid: IID of the alert to mutate.
        project_path: Project the alert to mutate is in (e.g., 'group/subgroup/project').
        client_mutation_id: A unique identifier for the client performing the mutation.
    """
    query = """
        mutation CreateAlertIssue($iid: String!, $projectPath: ID!, $clientMutationId: String) {
            createAlertIssue(input: {
                clientMutationId: $clientMutationId,
                iid: $iid,
                projectPath: $projectPath
            }) {
                alert {
                    id
                    iid
                    title
                    status
                    webUrl
                }
                clientMutationId
                errors
                issue {
                    id
                    iid
                    title
                    webUrl
                    state
                }
                todo {
                    id
                    state
                    action
                    body
                }
            }
        }
    """
    variables = {
        "iid": iid,
        "projectPath": project_path,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.createAnnotation ---
@mcp.tool()
def create_annotation(
    dashboard_path: str,
    description: str,
    starting_at: str,
    client_mutation_id: Optional[str] = None,
    cluster_id: Optional[str] = None,
    ending_at: Optional[str] = None,
    environment_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Creates a new annotation on a metrics dashboard.

    Args:
        dashboard_path (str): Path to a file defining the dashboard on which the annotation should be added.
        description (str): Description of the annotation.
        starting_at (str): Timestamp indicating starting moment to which the annotation relates.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        cluster_id (Optional[str]): Global ID of the cluster to add an annotation to.
        ending_at (Optional[str]): Timestamp indicating ending moment to which the annotation relates.
        environment_id (Optional[str]): Global ID of the environment to add an annotation to.
    """
    query = """
        mutation CreateAnnotation(
            $clientMutationId: String,
            $clusterId: ClustersClusterID,
            $dashboardPath: String!,
            $description: String!,
            $endingAt: Time,
            $environmentId: EnvironmentID,
            $startingAt: Time!
        ) {
            createAnnotation(input: {
                clientMutationId: $clientMutationId,
                clusterId: $clusterId,
                dashboardPath: $dashboardPath,
                description: $description,
                endingAt: $endingAt,
                environmentId: $environmentId,
                startingAt: $startingAt
            }) {
                annotation {
                    id
                    description
                    startingAt
                    endingAt
                    dashboardPath
                }
                clientMutationId
                errors
            }
        }
    """
    variables: Dict[str, Any] = {
        "dashboardPath": dashboard_path,
        "description": description,
        "startingAt": starting_at,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id
    if cluster_id is not None:
        variables["clusterId"] = cluster_id
    if ending_at is not None:
        variables["endingAt"] = ending_at
    if environment_id is not None:
        variables["environmentId"] = environment_id

    return _graphql_request(query, variables)

# --- Mutation.createBoard ---
from typing import Optional, List, Dict, Any

@mcp.tool()
def create_board(
    assignee_id: Optional[str] = None,
    client_mutation_id: Optional[str] = None,
    group_path: Optional[str] = None,
    hide_backlog_list: Optional[bool] = None,
    hide_closed_list: Optional[bool] = None,
    iteration_cadence_id: Optional[str] = None,
    iteration_id: Optional[str] = None,
    label_ids: Optional[List[str]] = None,
    labels: Optional[List[str]] = None,
    milestone_id: Optional[str] = None,
    name: Optional[str] = None,
    project_path: Optional[str] = None,
    weight: Optional[int] = None,
) -> Dict[str, Any]:
    """Creates a new GitLab board.

    Args:
        assignee_id: ID of user to be assigned to the board.
        client_mutation_id: A unique identifier for the client performing the mutation.
        group_path: Full path of the group with which the resource is associated.
        hide_backlog_list: Whether or not backlog list is hidden.
        hide_closed_list: Whether or not closed list is hidden.
        iteration_cadence_id: ID of iteration cadence to be assigned to the board.
        iteration_id: ID of iteration to be assigned to the board.
        label_ids: IDs of labels to be added to the board.
        labels: Labels of the issue.
        milestone_id: ID of milestone to be assigned to the board.
        name: Board name.
        project_path: Full path of the project with which the resource is associated.
        weight: Weight value to be assigned to the board.
    """
    mutation_args_list = []
    graphql_variables = {}
    graphql_variable_definitions = []

    if assignee_id is not None:
        mutation_args_list.append("assigneeId: $assigneeId")
        graphql_variables["assigneeId"] = assignee_id
        graphql_variable_definitions.append("$assigneeId: UserID")
    if client_mutation_id is not None:
        mutation_args_list.append("clientMutationId: $clientMutationId")
        graphql_variables["clientMutationId"] = client_mutation_id
        graphql_variable_definitions.append("$clientMutationId: String")
    if group_path is not None:
        mutation_args_list.append("groupPath: $groupPath")
        graphql_variables["groupPath"] = group_path
        graphql_variable_definitions.append("$groupPath: ID")
    if hide_backlog_list is not None:
        mutation_args_list.append("hideBacklogList: $hideBacklogList")
        graphql_variables["hideBacklogList"] = hide_backlog_list
        graphql_variable_definitions.append("$hideBacklogList: Boolean")
    if hide_closed_list is not None:
        mutation_args_list.append("hideClosedList: $hideClosedList")
        graphql_variables["hideClosedList"] = hide_closed_list
        graphql_variable_definitions.append("$hideClosedList: Boolean")
    if iteration_cadence_id is not None:
        mutation_args_list.append("iterationCadenceId: $iterationCadenceId")
        graphql_variables["iterationCadenceId"] = iteration_cadence_id
        graphql_variable_definitions.append("$iterationCadenceId: IterationsCadenceID")
    if iteration_id is not None:
        mutation_args_list.append("iterationId: $iterationId")
        graphql_variables["iterationId"] = iteration_id
        graphql_variable_definitions.append("$iterationId: IterationID")
    if label_ids is not None:
        mutation_args_list.append("labelIds: $labelIds")
        graphql_variables["labelIds"] = label_ids
        graphql_variable_definitions.append("$labelIds: [LabelID!]")
    if labels is not None:
        mutation_args_list.append("labels: $labels")
        graphql_variables["labels"] = labels
        graphql_variable_definitions.append("$labels: [String!]")
    if milestone_id is not None:
        mutation_args_list.append("milestoneId: $milestoneId")
        graphql_variables["milestoneId"] = milestone_id
        graphql_variable_definitions.append("$milestoneId: MilestoneID")
    if name is not None:
        mutation_args_list.append("name: $name")
        graphql_variables["name"] = name
        graphql_variable_definitions.append("$name: String")
    if project_path is not None:
        mutation_args_list.append("projectPath: $projectPath")
        graphql_variables["projectPath"] = project_path
        graphql_variable_definitions.append("$projectPath: ID")
    if weight is not None:
        mutation_args_list.append("weight: $weight")
        graphql_variables["weight"] = weight
        graphql_variable_definitions.append("$weight: Int")

    input_fields_str = ", ".join(mutation_args_list)
    
    variable_def_part = ""
    if graphql_variable_definitions:
        variable_def_part = f"({', '.join(graphql_variable_definitions)})"
    
    query = f"""
    mutation CreateBoardMutation{variable_def_part} {{
      createBoard(input: {{ {input_fields_str} }}) {{
        board {{
          id
          name
          state
          webUrl
          descriptionHtml
        }}
        clientMutationId
        errors
      }}
    }}
    """
    return _graphql_request(query, graphql_variables)

# --- Mutation.createBranch ---
@mcp.tool()
def create_branch(name: str, project_path: str, ref: str, client_mutation_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Creates a new branch in a GitLab project.

    Args:
        name: Name of the branch to create.
        project_path: Full path of the project.
        ref: Branch name or commit SHA to create the branch from.
        client_mutation_id: A unique identifier for the client performing the mutation.
    """
    query = """
    mutation createBranch($input: CreateBranchInput!) {
      createBranch(input: $input) {
        branch {
          id
          name
          webUrl
          commit {
            id
            sha
          }
        }
        clientMutationId
        errors
      }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "name": name,
            "projectPath": project_path,
            "ref": ref,
        }
    }
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.createClusterAgent ---
@mcp.tool()
def create_cluster_agent(
    name: str,
    project_path: str,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Creates a new cluster agent within a project.

    Args:
        name (str): Name of the cluster agent.
        project_path (str): Full path of the associated project for this cluster agent.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation CreateClusterAgent($name: String!, $projectPath: ID!, $clientMutationId: String) {
      createClusterAgent(input: {
        clientMutationId: $clientMutationId,
        name: $name,
        projectPath: $projectPath
      }) {
        clientMutationId
        clusterAgent {
          id
          name
          project {
            id
            fullPath
          }
        }
        errors
      }
    }
    """
    variables: Dict[str, Any] = {
        "name": name,
        "projectPath": project_path,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.createComplianceFramework ---
@mcp.tool()
def create_compliance_framework(namespace_path: str, params: Dict[str, Any], client_mutation_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Creates a new compliance framework for a given namespace.

    Args:
        namespace_path: Full path of the namespace to add the compliance framework to.
        params: Parameters to update the compliance framework with. Expected keys depend on ComplianceFrameworkInput.
        client_mutation_id: A unique identifier for the client performing the mutation.
    """
    query = """
    mutation CreateComplianceFramework($input: CreateComplianceFrameworkInput!) {
      createComplianceFramework(input: $input) {
        clientMutationId
        errors
        framework {
          id
          name
          description
          pipelineConfigurationFullPath
          isDefault
          complianceStandard
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "namespacePath": namespace_path,
            "params": params,
        }
    }
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.createCustomEmoji ---
@mcp.tool()
def create_custom_emoji(
    group_path: str,
    name: str,
    url: str,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Creates a new custom emoji for a given group.

    Args:
        group_path (str): Namespace full path the emoji is associated with.
        name (str): Name of the emoji.
        url (str): Location of the emoji file.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation CreateCustomEmoji($groupPath: ID!, $name: String!, $url: String!, $clientMutationId: String) {
      createCustomEmoji(input: {
        groupPath: $groupPath,
        name: $name,
        url: $url,
        clientMutationId: $clientMutationId
      }) {
        clientMutationId
        customEmoji {
          id
          name
          external
          url
          group {
            id
            fullPath
          }
        }
        errors
      }
    }
    """
    variables: Dict[str, Any] = {
        "groupPath": group_path,
        "name": name,
        "url": url,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.createDiffNote ---
@mcp.tool()
def create_diff_note(
    body: str,
    noteable_id: str,
    position: Dict[str, Any],
    client_mutation_id: Optional[str] = None,
    confidential: Optional[bool] = None,
    internal: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Creates a diff note on a GitLab resource.

    Args:
        body (str): Content of the note.
        noteable_id (str): Global ID of the resource to add a note to.
        position (Dict[str, Any]): Position of this note on a diff.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        confidential (Optional[bool]): Deprecated: Internal flag for a note. Please use `internal`.
        internal (Optional[bool]): Internal flag for a note.
    """
    from typing import Dict, Any, Optional

    query = """
    mutation createDiffNote($input: CreateDiffNoteInput!) {
      createDiffNote(input: $input) {
        clientMutationId
        errors
        note {
          id
          body
          createdAt
          author {
            id
            username
            name
          }
          position {
            filePath
            newPath
            oldPath
            oldLine
            newLine
            positionType
            headSha
            baseSha
            startSha
          }
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "body": body,
            "noteableId": noteable_id,
            "position": position,
        }
    }
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id
    if confidential is not None:
        variables["input"]["confidential"] = confidential
    if internal is not None:
        variables["input"]["internal"] = internal

    return _graphql_request(query, variables)

# --- Mutation.createEpic ---
@mcp.tool()
def create_epic(
    group_path: str,
    add_label_ids: Optional[List[str]] = None,
    add_labels: Optional[List[str]] = None,
    client_mutation_id: Optional[str] = None,
    color: Optional[str] = None,
    confidential: Optional[bool] = None,
    description: Optional[str] = None,
    due_date_fixed: Optional[str] = None,
    due_date_is_fixed: Optional[bool] = None,
    remove_label_ids: Optional[List[str]] = None,
    start_date_fixed: Optional[str] = None,
    start_date_is_fixed: Optional[bool] = None,
    title: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Creates a new epic within a specified group.

    Args:
        group_path (str): Group the epic to mutate is in.
        add_label_ids (Optional[List[str]]): IDs of labels to be added to the epic.
        add_labels (Optional[List[str]]): Array of labels to be added to the epic.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        color (Optional[str]): Color of the epic.
        confidential (Optional[bool]): Indicates if the epic is confidential.
        description (Optional[str]): Description of the epic.
        due_date_fixed (Optional[str]): End date of the epic.
        due_date_is_fixed (Optional[bool]): Indicates end date should be sourced from due_date_fixed field not the issue milestones.
        remove_label_ids (Optional[List[str]]): IDs of labels to be removed from the epic.
        start_date_fixed (Optional[str]): Start date of the epic.
        start_date_is_fixed (Optional[bool]): Indicates start date should be sourced from start_date_fixed field not the issue milestones.
        title (Optional[str]): Title of the epic.
    """
    input_variables: Dict[str, Any] = {
        "groupPath": group_path,
    }

    if add_label_ids is not None:
        input_variables["addLabelIds"] = add_label_ids
    if add_labels is not None:
        input_variables["addLabels"] = add_labels
    if client_mutation_id is not None:
        input_variables["clientMutationId"] = client_mutation_id
    if color is not None:
        input_variables["color"] = color
    if confidential is not None:
        input_variables["confidential"] = confidential
    if description is not None:
        input_variables["description"] = description
    if due_date_fixed is not None:
        input_variables["dueDateFixed"] = due_date_fixed
    if due_date_is_fixed is not None:
        input_variables["dueDateIsFixed"] = due_date_is_fixed
    if remove_label_ids is not None:
        input_variables["removeLabelIds"] = remove_label_ids
    if start_date_fixed is not None:
        input_variables["startDateFixed"] = start_date_fixed
    if start_date_is_fixed is not None:
        input_variables["startDateIsFixed"] = start_date_is_fixed
    if title is not None:
        input_variables["title"] = title

    variables = {"input": input_variables}

    query = """
    mutation CreateEpic($input: CreateEpicInput!) {
        createEpic(input: $input) {
            clientMutationId
            epic {
                id
                iid
                title
                descriptionHtml
                state
                webUrl
                startDate
                dueDate
                confidential
            }
            errors
        }
    }
    """
    return _graphql_request(query, variables)

# --- Mutation.createImageDiffNote ---
@mcp.tool()
def create_image_diff_note(
    body: str,
    noteable_id: str,
    position: Dict[str, Any],
    client_mutation_id: Optional[str] = None,
    confidential: Optional[bool] = None,
    internal: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Creates an image diff note on a noteable resource.

    Args:
        body (str): Content of the note.
        noteable_id (str): Global ID of the resource to add a note to.
        position (Dict[str, Any]): Position of this note on a diff. Expected keys include `baseSha`, `headSha`, `startSha`, `filePath`, `x`, `y`.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        confidential (Optional[bool]): **Deprecated:** This was renamed. Please use `internal`.
        internal (Optional[bool]): Internal flag for a note. Default is false.
    """
    query = """
    mutation CreateImageDiffNote(
      $body: String!,
      $noteableId: NoteableID!,
      $position: DiffImagePositionInput!,
      $clientMutationId: String,
      $confidential: Boolean,
      $internal: Boolean
    ) {
      createImageDiffNote(input: {
        body: $body,
        noteableId: $noteableId,
        position: $position,
        clientMutationId: $clientMutationId,
        confidential: $confidential,
        internal: $internal
      }) {
        clientMutationId
        errors
        note {
          id
          body
          createdAt
          url
          internal
          author {
            id
            username
            name
          }
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "body": body,
        "noteableId": noteable_id,
        "position": position,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id
    if confidential is not None:
        variables["confidential"] = confidential
    if internal is not None:
        variables["internal"] = internal

    return _graphql_request(query, variables)

# --- Mutation.createIssue ---
@mcp.tool()
def create_issue(
    project_path: str,
    title: str,
    assignee_ids: Optional[List[str]] = None,
    confidential: Optional[bool] = None,
    created_at: Optional[str] = None,
    description: Optional[str] = None,
    discussion_to_resolve: Optional[str] = None,
    due_date: Optional[str] = None,
    epic_id: Optional[str] = None,
    health_status: Optional[str] = None,
    iid: Optional[int] = None,
    iteration_cadence_id: Optional[str] = None,
    iteration_id: Optional[str] = None,
    iteration_wildcard_id: Optional[str] = None,
    label_ids: Optional[List[str]] = None,
    labels: Optional[List[str]] = None,
    locked: Optional[bool] = None,
    merge_request_to_resolve_discussions_of: Optional[str] = None,
    milestone_id: Optional[str] = None,
    move_after_id: Optional[str] = None,
    move_before_id: Optional[str] = None,
    issue_type: Optional[str] = None,
    weight: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Creates a new issue in a GitLab project.

    Args:
        project_path (str): Project full path the issue is associated with.
        title (str): Title of the issue.
        assignee_ids (Optional[List[str]]): Array of user IDs to assign to the issue.
        confidential (Optional[bool]): Indicates the issue is confidential.
        created_at (Optional[str]): Timestamp when the issue was created (ISO format).
        description (Optional[str]): Description of the issue.
        discussion_to_resolve (Optional[str]): ID of a discussion to resolve.
        due_date (Optional[str]): Due date of the issue (ISO8601Date format).
        epic_id (Optional[str]): ID of an epic to associate the issue with.
        health_status (Optional[str]): Desired health status.
        iid (Optional[int]): IID (internal ID) of a project issue.
        iteration_cadence_id (Optional[str]): Global iteration cadence ID.
        iteration_id (Optional[str]): Global iteration ID.
        iteration_wildcard_id (Optional[str]): Iteration wildcard ID (e.g., 'CURRENT').
        label_ids (Optional[List[str]]): IDs of labels to be added to the issue.
        labels (Optional[List[str]]): Labels of the issue.
        locked (Optional[bool]): Indicates discussion is locked on the issue.
        merge_request_to_resolve_discussions_of (Optional[str]): IID of a merge request for which to resolve discussions.
        milestone_id (Optional[str]): ID of the milestone to assign to the issue.
        move_after_id (Optional[str]): Global ID of issue that should be placed after the current issue.
        move_before_id (Optional[str]): Global ID of issue that should be placed before the current issue.
        issue_type (Optional[str]): Type of the issue.
        weight (Optional[int]): Weight of the issue.
    """
    _input: Dict[str, Any] = {
        "projectPath": project_path,
        "title": title,
    }
    if assignee_ids is not None:
        _input["assigneeIds"] = assignee_ids
    if confidential is not None:
        _input["confidential"] = confidential
    if created_at is not None:
        _input["createdAt"] = created_at
    if description is not None:
        _input["description"] = description
    if discussion_to_resolve is not None:
        _input["discussionToResolve"] = discussion_to_resolve
    if due_date is not None:
        _input["dueDate"] = due_date
    if epic_id is not None:
        _input["epicId"] = epic_id
    if health_status is not None:
        _input["healthStatus"] = health_status
    if iid is not None:
        _input["iid"] = iid
    if iteration_cadence_id is not None:
        _input["iterationCadenceId"] = iteration_cadence_id
    if iteration_id is not None:
        _input["iterationId"] = iteration_id
    if iteration_wildcard_id is not None:
        _input["iterationWildcardId"] = iteration_wildcard_id
    if label_ids is not None:
        _input["labelIds"] = label_ids
    if labels is not None:
        _input["labels"] = labels
    if locked is not None:
        _input["locked"] = locked
    if merge_request_to_resolve_discussions_of is not None:
        _input["mergeRequestToResolveDiscussionsOf"] = merge_request_to_resolve_discussions_of
    if milestone_id is not None:
        _input["milestoneId"] = milestone_id
    if move_after_id is not None:
        _input["moveAfterId"] = move_after_id
    if move_before_id is not None:
        _input["moveBeforeId"] = move_before_id
    if issue_type is not None:
        _input["type"] = issue_type  # GraphQL argument name is 'type'
    if weight is not None:
        _input["weight"] = weight

    query = """
        mutation CreateIssue($input: CreateIssueInput!) {
            createIssue(input: $input) {
                clientMutationId
                errors
                issue {
                    id
                    iid
                    title
                    description
                    state
                    webUrl
                    confidential
                    createdAt
                    dueDate
                    weight
                }
            }
        }
    """
    variables = {"input": _input}

    return _graphql_request(query, variables)

# --- Mutation.createIteration ---
@mcp.tool()
def create_iteration(
    client_mutation_id: Optional[str] = None,
    description: Optional[str] = None,
    due_date: Optional[str] = None,
    group_path: Optional[str] = None,
    iterations_cadence_id: Optional[str] = None,
    project_path: Optional[str] = None,
    start_date: Optional[str] = None,
    title: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Creates a new iteration.

    Args:
        client_mutation_id: A unique identifier for the client performing the mutation.
        description: Description of the iteration.
        due_date: End date of the iteration (e.g., "YYYY-MM-DD").
        group_path: Full path of the group with which the resource is associated.
        iterations_cadence_id: Global ID of the iteration cadence to be assigned to the new iteration.
        project_path: Full path of the project with which the resource is associated.
        start_date: Start date of the iteration (e.g., "YYYY-MM-DD").
        title: Title of the iteration.
    """
    from typing import Dict, Any, Optional

    query = """
    mutation CreateIteration($input: CreateIterationInput!) {
      createIteration(input: $input) {
        clientMutationId
        errors
        iteration {
          id
          title
          description
          startDate
          dueDate
          webUrl
          state
        }
      }
    }
    """
    variables: Dict[str, Any] = {"input": {}}
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id
    if description is not None:
        variables["input"]["description"] = description
    if due_date is not None:
        variables["input"]["dueDate"] = due_date
    if group_path is not None:
        variables["input"]["groupPath"] = group_path
    if iterations_cadence_id is not None:
        variables["input"]["iterationsCadenceId"] = iterations_cadence_id
    if project_path is not None:
        variables["input"]["projectPath"] = project_path
    if start_date is not None:
        variables["input"]["startDate"] = start_date
    if title is not None:
        variables["input"]["title"] = title

    return _graphql_request(query, variables)

# --- Mutation.createNote ---
@mcp.tool()
def create_note(
    body: str,
    noteable_id: str,
    client_mutation_id: Optional[str] = None,
    confidential: Optional[bool] = None,
    discussion_id: Optional[str] = None,
    internal: Optional[bool] = None,
    merge_request_diff_head_sha: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Creates a new note on a resource in GitLab.

    Args:
        body: Content of the note.
        noteable_id: Global ID of the resource to add a note to.
        client_mutation_id: A unique identifier for the client performing the mutation.
        confidential: Deprecated. Use `internal` instead.
        discussion_id: Global ID of the discussion this note is in reply to.
        internal: Internal flag for a note. Default is false.
        merge_request_diff_head_sha: SHA of the head commit to ensure the merge request has not been updated.
    """
    variables: Dict[str, Any] = {
        "body": body,
        "noteableId": noteable_id,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id
    if confidential is not None:
        variables["confidential"] = confidential
    if discussion_id is not None:
        variables["discussionId"] = discussion_id
    if internal is not None:
        variables["internal"] = internal
    if merge_request_diff_head_sha is not None:
        variables["mergeRequestDiffHeadSha"] = merge_request_diff_head_sha

    query = """
        mutation CreateNote(
            $body: String!,
            $noteableId: NoteableID!,
            $clientMutationId: String,
            $confidential: Boolean,
            $discussionId: DiscussionID,
            $internal: Boolean,
            $mergeRequestDiffHeadSha: String
        ) {
            createNote(input: {
                body: $body,
                noteableId: $noteableId,
                clientMutationId: $clientMutationId,
                confidential: $confidential,
                discussionId: $discussionId,
                internal: $internal,
                mergeRequestDiffHeadSha: $mergeRequestDiffHeadSha
            }) {
                clientMutationId
                errors
                note {
                    id
                    body
                    createdAt
                    author {
                        username
                        name
                    }
                    system
                }
            }
        }
    """
    return _graphql_request(query, variables)

# --- Mutation.createRequirement ---
@mcp.tool()
def create_requirement(
    project_path: str,
    client_mutation_id: Optional[str] = None,
    description: Optional[str] = None,
    title: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Creates a new requirement for a given project.

    Args:
        project_path: Full project path the requirement is associated with.
        client_mutation_id: A unique identifier for the client performing the mutation.
        description: Description of the requirement.
        title: Title of the requirement.
    """
    variables: Dict[str, Any] = {
        "input": {
            "projectPath": project_path,
        }
    }
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id
    if description is not None:
        variables["input"]["description"] = description
    if title is not None:
        variables["input"]["title"] = title

    query = """
    mutation createRequirementMutation($input: CreateRequirementInput!) {
      createRequirement(input: $input) {
        clientMutationId
        errors
        requirement {
          id
          title
          description
          state
        }
      }
    }
    """
    return _graphql_request(query, variables)

# --- Mutation.createSnippet ---
@mcp.tool()
def create_snippet(
    title: str,
    visibility_level: str,
    blob_actions: Optional[List[Dict[str, Any]]] = None,
    client_mutation_id: Optional[str] = None,
    description: Optional[str] = None,
    project_path: Optional[str] = None,
    uploaded_files: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Creates a new snippet in GitLab.

    Args:
        title: Title of the snippet.
        visibility_level: Visibility level of the snippet (e.g., "PRIVATE", "INTERNAL", "PUBLIC").
        blob_actions: Actions to perform over the snippet repository and blobs.
        client_mutation_id: A unique identifier for the client performing the mutation.
        description: Description of the snippet.
        project_path: Full path of the project the snippet is associated with.
        uploaded_files: Paths to files uploaded in the snippet description.
    """
    query = """
    mutation CreateSnippet($input: CreateSnippetInput!) {
      createSnippet(input: $input) {
        clientMutationId
        errors
        snippet {
          id
          title
          description
          webUrl
          visibilityLevel
          author {
            username
            webUrl
          }
          createdAt
          updatedAt
        }
      }
    }
    """

    _input: Dict[str, Any] = {
        "title": title,
        "visibilityLevel": visibility_level,
    }
    if blob_actions is not None:
        _input["blobActions"] = blob_actions
    if client_mutation_id is not None:
        _input["clientMutationId"] = client_mutation_id
    if description is not None:
        _input["description"] = description
    if project_path is not None:
        _input["projectPath"] = project_path
    if uploaded_files is not None:
        _input["uploadedFiles"] = uploaded_files

    variables = {"input": _input}

    return _graphql_request(query, variables)

# --- Mutation.createTestCase ---
@mcp.tool()
def create_test_case(
    project_path: str,
    title: str,
    client_mutation_id: Optional[str] = None,
    description: Optional[str] = None,
    label_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Creates a new test case within a specified GitLab project.

    Args:
        project_path (str): Full path of the project to create the test case in.
        title (str): The title of the test case.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        description (Optional[str]): Detailed description of the test case.
        label_ids (Optional[List[str]]): List of IDs of labels to be added to the test case.
    """
    query = """
    mutation CreateTestCase($input: CreateTestCaseInput!) {
      createTestCase(input: $input) {
        clientMutationId
        errors
        testCase {
          id
          iid
          title
          description
          state
          webUrl
          createdAt
          updatedAt
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "projectPath": project_path,
            "title": title,
        }
    }
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id
    if description is not None:
        variables["input"]["description"] = description
    if label_ids is not None:
        variables["input"]["labelIds"] = label_ids

    return _graphql_request(query, variables)

# --- Mutation.customerRelationsContactCreate ---
@mcp.tool()
def customer_relations_contact_create(
    first_name: str,
    group_id: str,
    last_name: str,
    client_mutation_id: Optional[str] = None,
    description: Optional[str] = None,
    email: Optional[str] = None,
    organization_id: Optional[str] = None,
    phone: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Creates a new customer relations contact in GitLab.

    Args:
        first_name (str): First name of the contact.
        group_id (str): Global ID of the group for the contact.
        last_name (str): Last name of the contact.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        description (Optional[str]): Description of or notes for the contact.
        email (Optional[str]): Email address of the contact.
        organization_id (Optional[str]): Global ID of the organization for the contact.
        phone (Optional[str]): Phone number of the contact.
    """
    query = """
        mutation CustomerRelationsContactCreate($input: CustomerRelationsContactCreateInput!) {
            customerRelationsContactCreate(input: $input) {
                clientMutationId
                contact {
                    id
                    firstName
                    lastName
                    email
                    phone
                    description
                    organization {
                        id
                        name
                    }
                    group {
                        id
                        name
                    }
                }
                errors
            }
        }
    """

    variables: Dict[str, Any] = {
        "input": {
            "firstName": first_name,
            "groupId": group_id,
            "lastName": last_name,
        }
    }

    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id
    if description is not None:
        variables["input"]["description"] = description
    if email is not None:
        variables["input"]["email"] = email
    if organization_id is not None:
        variables["input"]["organizationId"] = organization_id
    if phone is not None:
        variables["input"]["phone"] = phone

    return _graphql_request(query, variables)

# --- Mutation.customerRelationsContactUpdate ---
@mcp.tool()
def customer_relations_contact_update(
    id: str,
    active: Optional[bool] = None,
    client_mutation_id: Optional[str] = None,
    description: Optional[str] = None,
    email: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    organization_id: Optional[str] = None,
    phone: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Updates an existing customer relations contact.

    Args:
        id (str): Global ID of the contact.
        active (Optional[bool]): State of the contact.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        description (Optional[str]): Description of or notes for the contact.
        email (Optional[str]): Email address of the contact.
        first_name (Optional[str]): First name of the contact.
        last_name (Optional[str]): Last name of the contact.
        organization_id (Optional[str]): Organization of the contact.
        phone (Optional[str]): Phone number of the contact.
    """
    variables: Dict[str, Any] = {"id": id}
    input_fields = ["id: $id"]

    if active is not None:
        variables["active"] = active
        input_fields.append("active: $active")
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id
        input_fields.append("clientMutationId: $clientMutationId")
    if description is not None:
        variables["description"] = description
        input_fields.append("description: $description")
    if email is not None:
        variables["email"] = email
        input_fields.append("email: $email")
    if first_name is not None:
        variables["firstName"] = first_name
        input_fields.append("firstName: $firstName")
    if last_name is not None:
        variables["lastName"] = last_name
        input_fields.append("lastName: $lastName")
    if organization_id is not None:
        variables["organizationId"] = organization_id
        input_fields.append("organizationId: $organizationId")
    if phone is not None:
        variables["phone"] = phone
        input_fields.append("phone: $phone")

    # Construct variable definitions for the GraphQL mutation
    variable_definitions = ", ".join([
        "$id: CustomerRelationsContactID!",
        *([f"$active: Boolean"] if active is not None else []),
        *([f"$clientMutationId: String"] if client_mutation_id is not None else []),
        *([f"$description: String"] if description is not None else []),
        *([f"$email: String"] if email is not None else []),
        *([f"$firstName: String"] if first_name is not None else []),
        *([f"$lastName: String"] if last_name is not None else []),
        *([f"$organizationId: CustomerRelationsOrganizationID"] if organization_id is not None else []),
        *([f"$phone: String"] if phone is not None else []),
    ])

    input_str = ", ".join(input_fields)

    query = f"""
    mutation CustomerRelationsContactUpdate({variable_definitions}) {{
      customerRelationsContactUpdate(input: {{ {input_str} }}) {{
        clientMutationId
        contact {{
          id
          firstName
          lastName
          email
          phone
          active
          description
          organization {{
            id
            name
          }}
        }}
        errors
      }}
    }}
    """
    return _graphql_request(query, variables)

# --- Mutation.customerRelationsOrganizationCreate ---
@mcp.tool()
def customer_relations_organization_create(
    group_id: str,
    name: str,
    client_mutation_id: Optional[str] = None,
    default_rate: Optional[float] = None,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    """Creates a new customer relations organization.

    Args:
        group_id: Group for the organization.
        name: Name of the organization.
        client_mutation_id: A unique identifier for the client performing the mutation.
        default_rate: Standard billing rate for the organization.
        description: Description of or notes for the organization.
    """
    query = """
    mutation customerRelationsOrganizationCreateMutation(
      $clientMutationId: String
      $defaultRate: Float
      $description: String
      $groupId: GroupID!
      $name: String!
    ) {
      customerRelationsOrganizationCreate(input: {
        clientMutationId: $clientMutationId
        defaultRate: $defaultRate
        description: $description
        groupId: $groupId
        name: $name
      }) {
        clientMutationId
        errors
        organization {
          id
          name
          description
          defaultRate
          group {
            id
            name
            fullName
          }
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "groupId": group_id,
        "name": name,
        "clientMutationId": client_mutation_id,
        "defaultRate": default_rate,
        "description": description,
    }
    return _graphql_request(query, variables)

# --- Mutation.customerRelationsOrganizationUpdate ---
@mcp.tool()
def customer_relations_organization_update(
    id: str,
    active: Optional[bool] = None,
    client_mutation_id: Optional[str] = None,
    default_rate: Optional[float] = None,
    description: Optional[str] = None,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Updates an existing customer relations organization.

    Args:
        id (str): Global ID of the organization.
        active (Optional[bool]): State of the organization.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        default_rate (Optional[float]): Standard billing rate for the organization.
        description (Optional[str]): Description of or notes for the organization.
        name (Optional[str]): Name of the organization.
    """
    query = """
    mutation customerRelationsOrganizationUpdate(
      $id: CustomerRelationsOrganizationID!
      $active: Boolean
      $clientMutationId: String
      $defaultRate: Float
      $description: String
      $name: String
    ) {
      customerRelationsOrganizationUpdate(input: {
        id: $id
        active: $active
        clientMutationId: $clientMutationId
        defaultRate: $defaultRate
        description: $description
        name: $name
      }) {
        clientMutationId
        errors
        organization {
          id
          name
          description
          active
          defaultRate
        }
      }
    }
    """
    variables: Dict[str, Any] = {"id": id}
    if active is not None:
        variables["active"] = active
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id
    if default_rate is not None:
        variables["defaultRate"] = default_rate
    if description is not None:
        variables["description"] = description
    if name is not None:
        variables["name"] = name

    return _graphql_request(query, variables)

# --- Mutation.dastOnDemandScanCreate ---
@mcp.tool()
def dast_on_demand_scan_create(
    dast_site_profile_id: str,
    full_path: str,
    client_mutation_id: Optional[str] = None,
    dast_scanner_profile_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Creates a DAST on-demand scan.

    Args:
        dast_site_profile_id (str): ID of the site profile to be used for the scan.
        full_path (str): Project the site profile belongs to.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        dast_scanner_profile_id (Optional[str]): ID of the scanner profile to be used for the scan.
    """
    query = """
    mutation DastOnDemandScanCreate($clientMutationId: String, $dastScannerProfileId: DastScannerProfileID, $dastSiteProfileId: DastSiteProfileID!, $fullPath: ID!) {
      dastOnDemandScanCreate(input: {
        clientMutationId: $clientMutationId,
        dastScannerProfileId: $dastScannerProfileId,
        dastSiteProfileId: $dastSiteProfileId,
        fullPath: $fullPath
      }) {
        clientMutationId
        errors
        pipelineUrl
      }
    }
    """
    variables: Dict[str, Any] = {
        "dastSiteProfileId": dast_site_profile_id,
        "fullPath": full_path,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id
    if dast_scanner_profile_id is not None:
        variables["dastScannerProfileId"] = dast_scanner_profile_id

    return _graphql_request(query, variables)

# --- Mutation.dastProfileCreate ---
@mcp.tool()
def dast_profile_create(
    full_path: str,
    name: str,
    dast_scanner_profile_id: str,
    dast_site_profile_id: str,
    branch_name: Optional[str] = None,
    client_mutation_id: Optional[str] = None,
    dast_profile_schedule: Optional[Dict[str, Any]] = None,
    description: Optional[str] = None,
    run_after_create: Optional[bool] = None,
) -> Dict[str, Any]:
    """Creates a DAST profile for a project.

    Args:
        full_path (str): Project the profile belongs to.
        name (str): Name of the profile.
        dast_scanner_profile_id (str): ID of the scanner profile to be associated.
        dast_site_profile_id (str): ID of the site profile to be associated.
        branch_name (Optional[str]): Associated branch.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        dast_profile_schedule (Optional[Dict[str, Any]]): Represents a DAST Profile Schedule.
        description (Optional[str]): Description of the profile.
        run_after_create (Optional[bool]): Run scan using profile after creation.
    """
    query = """
    mutation DastProfileCreate($input: DastProfileCreateInput!) {
      dastProfileCreate(input: $input) {
        clientMutationId
        dastProfile {
          id
          name
          description
          branchName
          runAfterCreate
          dastSiteProfile {
            id
            name
          }
          dastScannerProfile {
            id
            name
          }
        }
        errors
        pipelineUrl
      }
    }
    """
    variables = {
        "input": {
            "fullPath": full_path,
            "name": name,
            "dastScannerProfileId": dast_scanner_profile_id,
            "dastSiteProfileId": dast_site_profile_id,
        }
    }
    if branch_name is not None:
        variables["input"]["branchName"] = branch_name
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id
    if dast_profile_schedule is not None:
        variables["input"]["dastProfileSchedule"] = dast_profile_schedule
    if description is not None:
        variables["input"]["description"] = description
    if run_after_create is not None:
        variables["input"]["runAfterCreate"] = run_after_create

    return _graphql_request(query, variables)

# --- Mutation.dastProfileDelete ---
@mcp.tool()
def dast_profile_delete(id: str, client_mutation_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Deletes a DAST profile by its ID.

    Args:
        id (str): ID of the profile to be deleted.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation DastProfileDelete($id: DastProfileID!, $clientMutationId: String) {
      dastProfileDelete(input: { id: $id, clientMutationId: $clientMutationId }) {
        clientMutationId
        errors
      }
    }
    """
    variables: Dict[str, Any] = {
        "id": id,
        "clientMutationId": client_mutation_id,
    }
    return _graphql_request(query, variables)

# --- Mutation.dastProfileRun ---
@mcp.tool()
def dast_profile_run(
    id: str,
    client_mutation_id: Optional[str] = None,
    full_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Runs a DAST profile to initiate a scan.

    Args:
        id (str): ID of the profile to be used for the scan.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        full_path (Optional[str]): **Deprecated:** Full path not required to qualify Global ID.
    """
    query = """
    mutation DastProfileRun($id: DastProfileID!, $clientMutationId: String, $fullPath: ID) {
      dastProfileRun(input: {
        id: $id,
        clientMutationId: $clientMutationId,
        fullPath: $fullPath
      }) {
        clientMutationId
        errors
        pipelineUrl
      }
    }
    """
    variables: Dict[str, Any] = {
        "id": id,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id
    if full_path is not None:
        variables["fullPath"] = full_path

    return _graphql_request(query, variables)

# --- Mutation.dastProfileUpdate ---
@mcp.tool()
def dast_profile_update(
    id: str,
    branch_name: Optional[str] = None,
    client_mutation_id: Optional[str] = None,
    dast_profile_schedule: Optional[Dict[str, Any]] = None,
    dast_scanner_profile_id: Optional[str] = None,
    dast_site_profile_id: Optional[str] = None,
    description: Optional[str] = None,
    full_path: Optional[str] = None,
    name: Optional[str] = None,
    run_after_update: Optional[bool] = None,
) -> Dict[str, Any]:
    """Updates an existing DAST profile.

    Args:
        id (str): ID of the profile to be updated.
        branch_name (Optional[str]): Associated branch.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        dast_profile_schedule (Optional[Dict[str, Any]]): Represents a DAST profile schedule configuration.
        dast_scanner_profile_id (Optional[str]): ID of the scanner profile to be associated.
        dast_site_profile_id (Optional[str]): ID of the site profile to be associated.
        description (Optional[str]): Description of the profile. Defaults to an empty string.
        full_path (Optional[str]): Deprecated: Full path not required to qualify Global ID.
        name (Optional[str]): Name of the profile.
        run_after_update (Optional[bool]): Run scan using profile after update. Defaults to false.
    """
    query = """
    mutation DastProfileUpdate($input: DastProfileUpdateInput!) {
      dastProfileUpdate(input: $input) {
        clientMutationId
        dastProfile {
          id
          name
          description
          branchName
          runAfterUpdate
          dastScannerProfile {
            id
            name
          }
          dastSiteProfile {
            id
            name
          }
          dastProfileSchedule {
            active
            cadence
            dailyWeekly {
              day
              time
            }
            monthly {
              dayOfMonth
              time
            }
            timezone
          }
        }
        errors
        pipelineUrl
      }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "id": id,
        }
    }
    if branch_name is not None:
        variables["input"]["branchName"] = branch_name
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id
    if dast_profile_schedule is not None:
        variables["input"]["dastProfileSchedule"] = dast_profile_schedule
    if dast_scanner_profile_id is not None:
        variables["input"]["dastScannerProfileId"] = dast_scanner_profile_id
    if dast_site_profile_id is not None:
        variables["input"]["dastSiteProfileId"] = dast_site_profile_id
    if description is not None:
        variables["input"]["description"] = description
    if full_path is not None:
        variables["input"]["fullPath"] = full_path
    if name is not None:
        variables["input"]["name"] = name
    if run_after_update is not None:
        variables["input"]["runAfterUpdate"] = run_after_update

    return _graphql_request(query, variables)

# --- Mutation.dastScannerProfileCreate ---
@mcp.tool()
def dast_scanner_profile_create(
    full_path: str,
    profile_name: str,
    client_mutation_id: Optional[str] = None,
    scan_type: Optional[str] = None,
    show_debug_messages: Optional[bool] = None,
    spider_timeout: Optional[int] = None,
    target_timeout: Optional[int] = None,
    use_ajax_spider: Optional[bool] = None,
) -> Dict[str, Any]:
    """Creates a new DAST scanner profile for a project.

    Args:
        full_path (str): Project the scanner profile belongs to.
        profile_name (str): Name of the scanner profile.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        scan_type (Optional[str]): Indicates the type of DAST scan that will run. Either a Passive Scan or an Active Scan.
        show_debug_messages (Optional[bool]): Indicates if debug messages should be included in DAST console output.
        spider_timeout (Optional[int]): Maximum number of minutes allowed for the spider to traverse the site.
        target_timeout (Optional[int]): Maximum number of seconds allowed for the site under test to respond to a request.
        use_ajax_spider (Optional[bool]): Indicates if the AJAX spider should be used to crawl the target site.
    """
    query = """
        mutation DastScannerProfileCreate(
            $clientMutationId: String,
            $fullPath: ID!,
            $profileName: String!,
            $scanType: DastScanTypeEnum,
            $showDebugMessages: Boolean,
            $spiderTimeout: Int,
            $targetTimeout: Int,
            $useAjaxSpider: Boolean
        ) {
            dastScannerProfileCreate(input: {
                clientMutationId: $clientMutationId,
                fullPath: $fullPath,
                profileName: $profileName,
                scanType: $scanType,
                showDebugMessages: $showDebugMessages,
                spiderTimeout: $spiderTimeout,
                targetTimeout: $targetTimeout,
                useAjaxSpider: $useAjaxSpider
            }) {
                clientMutationId
                dastScannerProfile {
                    id
                    name
                    scanType
                    showDebugMessages
                    spiderTimeout
                    targetTimeout
                    useAjaxSpider
                }
                errors
            }
        }
    """
    variables: Dict[str, Any] = {
        "fullPath": full_path,
        "profileName": profile_name,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id
    if scan_type is not None:
        variables["scanType"] = scan_type
    if show_debug_messages is not None:
        variables["showDebugMessages"] = show_debug_messages
    if spider_timeout is not None:
        variables["spiderTimeout"] = spider_timeout
    if target_timeout is not None:
        variables["targetTimeout"] = target_timeout
    if use_ajax_spider is not None:
        variables["useAjaxSpider"] = use_ajax_spider

    return _graphql_request(query, variables)

# --- Mutation.dastScannerProfileDelete ---
@mcp.tool()
def dast_scanner_profile_delete(
    id: str,
    client_mutation_id: Optional[str] = None,
    full_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Deletes a DAST scanner profile.

    Args:
        id (str): ID of the scanner profile to be deleted.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        full_path (Optional[str]): Full path not required to qualify Global ID. Deprecated in 14.5.
    """
    query = """
    mutation DastScannerProfileDelete($input: DastScannerProfileDeleteInput!) {
      dastScannerProfileDelete(input: $input) {
        clientMutationId
        errors
      }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "id": id,
        }
    }
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id
    if full_path is not None:
        variables["input"]["fullPath"] = full_path

    return _graphql_request(query, variables)

# --- Mutation.dastScannerProfileUpdate ---
@mcp.tool()
def dast_scanner_profile_update(
    profile_id: str,
    profile_name: str,
    spider_timeout: int,
    target_timeout: int,
    client_mutation_id: Optional[str] = None,
    full_path: Optional[str] = None,
    scan_type: Optional[str] = None,
    show_debug_messages: Optional[bool] = None,
    use_ajax_spider: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Updates an existing DAST scanner profile.

    Args:
        profile_id: ID of the scanner profile to be updated.
        profile_name: Name of the scanner profile.
        spider_timeout: Maximum number of minutes allowed for the spider to traverse the site.
        target_timeout: Maximum number of seconds allowed for the site under test to respond to a request.
        client_mutation_id: A unique identifier for the client performing the mutation.
        full_path: Deprecated: Full path not required to qualify Global ID.
        scan_type: Indicates the type of DAST scan that will run.
        show_debug_messages: True to include debug messages in DAST console output.
        use_ajax_spider: True to run the AJAX spider in addition to the traditional spider.
    """
    query = """
    mutation DastScannerProfileUpdate($input: DastScannerProfileUpdateInput!) {
      dastScannerProfileUpdate(input: $input) {
        clientMutationId
        dastScannerProfile {
          id
          name
          scanType
          showDebugMessages
          spiderTimeout
          targetTimeout
          useAjaxSpider
        }
        errors
      }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "id": profile_id,
            "profileName": profile_name,
            "spiderTimeout": spider_timeout,
            "targetTimeout": target_timeout,
        }
    }
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id
    if full_path is not None:
        variables["input"]["fullPath"] = full_path
    if scan_type is not None:
        variables["input"]["scanType"] = scan_type
    if show_debug_messages is not None:
        variables["input"]["showDebugMessages"] = show_debug_messages
    if use_ajax_spider is not None:
        variables["input"]["useAjaxSpider"] = use_ajax_spider

    return _graphql_request(query, variables)

# --- Mutation.dastSiteProfileCreate ---
@mcp.tool()
def dast_site_profile_create(
    full_path: str,
    profile_name: str,
    auth: Optional[Dict[str, Any]] = None,
    client_mutation_id: Optional[str] = None,
    excluded_urls: Optional[List[List[str]]] = None,
    request_headers: Optional[str] = None,
    scan_file_path: Optional[str] = None,
    scan_method: Optional[str] = None,
    target_type: Optional[str] = None,
    target_url: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Creates a DAST site profile for a project.

    Args:
        full_path (str): Project the site profile belongs to.
        profile_name (str): Name of the site profile.
        auth (Optional[Dict[str, Any]]): Parameters for authentication.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        excluded_urls (Optional[List[List[str]]]): URLs to skip during an authenticated scan.
        request_headers (Optional[str]): Comma-separated list of request header names and values to be added to every request made by DAST.
        scan_file_path (Optional[str]): File Path or URL used as input for the scan method.
        scan_method (Optional[str]): Scan method by the scanner (e.g., 'HAR', 'OPENAPI', 'POSTMAN').
        target_type (Optional[str]): Type of target to be scanned (e.g., 'WEBSITE').
        target_url (Optional[str]): URL of the target to be scanned.
    """
    query = """
    mutation DastSiteProfileCreate(
      $auth: DastSiteProfileAuthInput,
      $clientMutationId: String,
      $excludedUrls: [[String!]],
      $fullPath: ID!,
      $profileName: String!,
      $requestHeaders: String,
      $scanFilePath: String,
      $scanMethod: DastScanMethodType,
      $targetType: DastTargetTypeEnum,
      $targetUrl: String
    ) {
      dastSiteProfileCreate(input: {
        auth: $auth,
        clientMutationId: $clientMutationId,
        excludedUrls: $excludedUrls,
        fullPath: $fullPath,
        profileName: $profileName,
        requestHeaders: $requestHeaders,
        scanFilePath: $scanFilePath,
        scanMethod: $scanMethod,
        targetType: $targetType,
        targetUrl: $targetUrl
      }) {
        clientMutationId
        dastSiteProfile {
          id
          name
          fullPath
          targetUrl
          targetType
          scanMethod
          requestHeaders
          scanFilePath
          excludedUrls
        }
        errors
        id
      }
    }
    """
    variables = {
        "fullPath": full_path,
        "profileName": profile_name,
        "auth": auth,
        "clientMutationId": client_mutation_id,
        "excludedUrls": excluded_urls,
        "requestHeaders": request_headers,
        "scanFilePath": scan_file_path,
        "scanMethod": scan_method,
        "targetType": target_type,
        "targetUrl": target_url,
    }
    return _graphql_request(query, variables)

# --- Mutation.dastSiteProfileDelete ---
@mcp.tool()
def dast_site_profile_delete(
    id: str,
    client_mutation_id: Optional[str] = None,
    full_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Deletes a DAST site profile from GitLab.

    Args:
        id (str): ID of the site profile to be deleted.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        full_path (Optional[str]): Full path not required to qualify Global ID (deprecated).
    """
    query = """
    mutation DastSiteProfileDelete($input: DastSiteProfileDeleteInput!) {
      dastSiteProfileDelete(input: $input) {
        clientMutationId
        errors
      }
    }
    """
    input_dict = {
        "id": id,
    }
    if client_mutation_id is not None:
        input_dict["clientMutationId"] = client_mutation_id
    if full_path is not None:
        input_dict["fullPath"] = full_path

    variables = {"input": input_dict}
    return _graphql_request(query, variables)

# --- Mutation.dastSiteProfileUpdate ---
@mcp.tool()
def dast_site_profile_update(
    id: str,
    profile_name: str,
    auth: Optional[Dict[str, Any]] = None,
    client_mutation_id: Optional[str] = None,
    excluded_urls: Optional[List[List[str]]] = None,
    full_path: Optional[str] = None,
    request_headers: Optional[str] = None,
    scan_file_path: Optional[str] = None,
    scan_method: Optional[str] = None,
    target_type: Optional[str] = None,
    target_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Updates an existing DAST site profile.

    Args:
        id (str): ID of the site profile to be updated.
        profile_name (str): Name of the site profile.
        auth (Optional[Dict[str, Any]]): Parameters for authentication.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        excluded_urls (Optional[List[List[str]]]): URLs to skip during an authenticated scan.
        full_path (Optional[str]): **Deprecated:** Full path not required to qualify Global ID.
        request_headers (Optional[str]): Comma-separated list of request header names and values.
        scan_file_path (Optional[str]): File Path or URL used as input for the scan method.
        scan_method (Optional[str]): Scan method by the scanner.
        target_type (Optional[str]): Type of target to be scanned.
        target_url (Optional[str]): URL of the target to be scanned.

    Returns:
        Dict[str, Any]: The response from the GraphQL mutation, including the updated site profile and any errors.
    """
    query = """
    mutation DastSiteProfileUpdate(
      $auth: DastSiteProfileAuthInput,
      $clientMutationId: String,
      $excludedUrls: [[String!]],
      $fullPath: ID,
      $id: DastSiteProfileID!,
      $profileName: String!,
      $requestHeaders: String,
      $scanFilePath: String,
      $scanMethod: DastScanMethodType,
      $targetType: DastTargetTypeEnum,
      $targetUrl: String
    ) {
      dastSiteProfileUpdate(input: {
        auth: $auth,
        clientMutationId: $clientMutationId,
        excludedUrls: $excludedUrls,
        fullPath: $fullPath,
        id: $id,
        profileName: $profileName,
        requestHeaders: $requestHeaders,
        scanFilePath: $scanFilePath,
        scanMethod: $scanMethod,
        targetType: $targetType,
        targetUrl: $targetUrl
      }) {
        clientMutationId
        dastSiteProfile {
          id
          name
          targetUrl
          scanMethod
          targetType
        }
        errors
        id
      }
    }
    """
    variables: Dict[str, Any] = {
        "id": id,
        "profileName": profile_name,
    }
    if auth is not None:
        variables["auth"] = auth
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id
    if excluded_urls is not None:
        variables["excludedUrls"] = excluded_urls
    if full_path is not None:
        variables["fullPath"] = full_path
    if request_headers is not None:
        variables["requestHeaders"] = request_headers
    if scan_file_path is not None:
        variables["scanFilePath"] = scan_file_path
    if scan_method is not None:
        variables["scanMethod"] = scan_method
    if target_type is not None:
        variables["targetType"] = target_type
    if target_url is not None:
        variables["targetUrl"] = target_url

    return _graphql_request(query, variables)

# --- Mutation.dastSiteTokenCreate ---
@mcp.tool()
def dast_site_token_create(
    full_path: str,
    client_mutation_id: Optional[str] = None,
    target_url: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Creates a DAST site token for a project.

    Args:
        full_path (str): Project the site token belongs to.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        target_url (Optional[str]): URL of the target to be validated.
    """
    query = """
    mutation DastSiteTokenCreate(
      $clientMutationId: String,
      $fullPath: ID!,
      $targetUrl: String
    ) {
      dastSiteTokenCreate(input: {
        clientMutationId: $clientMutationId,
        fullPath: $fullPath,
        targetUrl: $targetUrl
      }) {
        clientMutationId
        errors
        id
        status
        token
      }
    }
    """
    variables: Dict[str, Any] = {
        "fullPath": full_path,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id
    if target_url is not None:
        variables["targetUrl"] = target_url

    return _graphql_request(query, variables)

# --- Mutation.dastSiteValidationCreate ---
@mcp.tool()
def dast_site_validation_create(
    dast_site_token_id: str,
    full_path: str,
    validation_path: str,
    client_mutation_id: Optional[str] = None,
    strategy: Optional[str] = None,
) -> Dict[str, Any]:
    """Creates a DAST site validation.

    Args:
        dast_site_token_id (str): ID of the site token.
        full_path (str): Project the site profile belongs to.
        validation_path (str): Path to be requested during validation.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        strategy (Optional[str]): Validation strategy to be used.
    """
    mutation_variables = {
        "dastSiteTokenId": dast_site_token_id,
        "fullPath": full_path,
        "validationPath": validation_path,
    }
    input_fields_str_parts = [
        "dastSiteTokenId: $dastSiteTokenId",
        "fullPath: $fullPath",
        "validationPath: $validationPath",
    ]
    variable_definitions_parts = [
        "$dastSiteTokenId: DastSiteTokenID!",
        "$fullPath: ID!",
        "$validationPath: String!",
    ]

    if client_mutation_id is not None:
        mutation_variables["clientMutationId"] = client_mutation_id
        input_fields_str_parts.append("clientMutationId: $clientMutationId")
        variable_definitions_parts.append("$clientMutationId: String")
    if strategy is not None:
        mutation_variables["strategy"] = strategy
        input_fields_str_parts.append("strategy: $strategy")
        variable_definitions_parts.append("$strategy: DastSiteValidationStrategyEnum")

    input_graphql_str = ", ".join(input_fields_str_parts)
    variable_definitions_graphql_str = ", ".join(variable_definitions_parts)

    query = f"""
    mutation DastSiteValidationCreate({variable_definitions_graphql_str}) {{
        dastSiteValidationCreate(input: {{ {input_graphql_str} }}) {{
            clientMutationId
            errors
            id
            status
        }}
    }}
    """
    return _graphql_request(query, mutation_variables)

# --- Mutation.dastSiteValidationRevoke ---
@mcp.tool()
def dast_site_validation_revoke(
    full_path: str,
    normalized_target_url: str,
    client_mutation_id: Optional[str] = None,
    graphql_variables: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Revokes a DAST site validation.

    Args:
        full_path: Project the site validation belongs to.
        normalized_target_url: Normalized URL of the target to be revoked.
        client_mutation_id: A unique identifier for the client performing the mutation.
    """
    query = """
    mutation dastSiteValidationRevokeMutation($input: DastSiteValidationRevokeInput!) {
      dastSiteValidationRevoke(input: $input) {
        clientMutationId
        errors
      }
    }
    """
    graphql_variables: Dict[str, Any] = {
        "input": {
            "fullPath": full_path,
            "normalizedTargetUrl": normalized_target_url,
        }
    }
    if client_mutation_id is not None:
        graphql_variables["input"]["clientMutationId"] = client_mutation_id
    if graphql_variables is not None:
        graphql_variables.update(graphql_variables)
    return _graphql_request(query, variables=graphql_variables)

# --- Mutation.deleteAnnotation ---
@mcp.tool()
def delete_annotation(
    id: str,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Deletes an annotation from a GitLab metrics dashboard.

    Args:
        id: Global ID of the annotation to delete.
        client_mutation_id: A unique identifier for the client performing the mutation.
    """
    query = """
        mutation DeleteAnnotation($id: MetricsDashboardAnnotationID!, $clientMutationId: String) {
            deleteAnnotation(input: { id: $id, clientMutationId: $clientMutationId }) {
                clientMutationId
                errors
            }
        }
    """
    variables: Dict[str, Any] = {
        "id": id,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.designManagementDelete ---
@mcp.tool()
def design_management_delete(
    filenames: List[List[str]],
    iid: str,
    project_path: str,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Deletes specified designs from an issue.

    Args:
        filenames: Filenames of the designs to delete.
        iid: IID of the issue to modify designs for.
        project_path: Project where the issue is located.
        client_mutation_id: A unique identifier for the client performing the mutation.
    """
    query = """
    mutation DesignManagementDelete(
      $clientMutationId: String
      $filenames: [[String!]!]!
      $iid: ID!
      $projectPath: ID!
    ) {
      designManagementDelete(input: {
        clientMutationId: $clientMutationId
        filenames: $filenames
        iid: $iid
        projectPath: $projectPath
      }) {
        clientMutationId
        errors
        version {
          id
          sha
          createdAt
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "filenames": filenames,
        "iid": iid,
        "projectPath": project_path,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.designManagementMove ---
@mcp.tool()
def design_management_move(
    id: str,
    client_mutation_id: Optional[str] = None,
    next_design_id: Optional[str] = None,
    previous_design_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Moves a design within a collection.

    Args:
        id (str): ID of the design to move.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        next_design_id (Optional[str]): ID of the immediately following design.
        previous_design_id (Optional[str]): ID of the immediately preceding design.
    """
    query = """
    mutation DesignManagementMove($input: DesignManagementMoveInput!) {
      designManagementMove(input: $input) {
        clientMutationId
        designCollection {
          id
          designs {
            nodes {
              id
              filename
              fullPath
              image
              diffRefs {
                baseSha
                headSha
                startSha
              }
            }
            pageInfo {
              endCursor
              hasNextPage
            }
          }
        }
        errors
      }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "id": id,
        }
    }
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id
    if next_design_id is not None:
        variables["input"]["next"] = next_design_id
    if previous_design_id is not None:
        variables["input"]["previous"] = previous_design_id

    return _graphql_request(query, variables)

# --- Mutation.designManagementUpload ---
@mcp.tool()
def design_management_upload(
    files: List[Any],
    iid: str,
    project_path: str,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Uploads new designs to an issue or updates existing ones.

    Args:
        files: Files to upload.
        iid: IID of the issue to modify designs for.
        project_path: Project where the issue is to upload designs for.
        client_mutation_id: A unique identifier for the client performing the mutation.
    """
    query = """
    mutation DesignManagementUpload(
        $files: [Upload!]!,
        $iid: ID!,
        $projectPath: ID!,
        $clientMutationId: String
    ) {
        designManagementUpload(input: {
            files: $files,
            iid: $iid,
            projectPath: $projectPath,
            clientMutationId: $clientMutationId
        }) {
            clientMutationId
            designs {
                id
                filename
                fullPath
                image {
                    webUrl
                }
            }
            errors
            skippedDesigns {
                id
                filename
                fullPath
                image {
                    webUrl
                }
            }
        }
    }
    """
    variables = {
        "files": files,
        "iid": iid,
        "projectPath": project_path,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.destroyBoard ---
@mcp.tool()
def destroy_board(board_id: str, client_mutation_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Destroys a GitLab board.

    Args:
        board_id: Global ID of the board to destroy.
        client_mutation_id: A unique identifier for the client performing the mutation.
    """
    query = """
    mutation DestroyBoard($id: BoardID!, $clientMutationId: String) {
      destroyBoard(input: { id: $id, clientMutationId: $clientMutationId }) {
        board {
          id
          name
          webUrl
        }
        clientMutationId
        errors
      }
    }
    """
    variables: Dict[str, Any] = {"id": board_id}
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.destroyBoardList ---
@mcp.tool()
def destroy_board_list(list_id: str, client_mutation_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Destroys a board list in GitLab.

    Args:
        list_id (str): Global ID of the list to destroy. Only label lists are accepted.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation destroyBoardListMutation($list_id: ListID!, $client_mutation_id: String) {
      destroyBoardList(input: { listId: $list_id, clientMutationId: $client_mutation_id }) {
        clientMutationId
        errors
        list {
          id
          title
          listType
          position
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "list_id": list_id,
    }
    if client_mutation_id is not None:
        variables["client_mutation_id"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.destroyComplianceFramework ---
@mcp.tool()
def destroy_compliance_framework(
    framework_id: str,
    client_mutation_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Destroys a compliance framework in GitLab.

    Args:
        framework_id: Global ID of the compliance framework to destroy.
        client_mutation_id: A unique identifier for the client performing the mutation.
    """
    query = """
    mutation destroyComplianceFramework($input: DestroyComplianceFrameworkInput!) {
      destroyComplianceFramework(input: $input) {
        clientMutationId
        errors
      }
    }
    """
    variables_input = {
        "id": framework_id
    }
    if client_mutation_id is not None:
        variables_input["clientMutationId"] = client_mutation_id

    variables = {
        "input": variables_input
    }
    return _graphql_request(query, variables)

# --- Mutation.destroyContainerRepository ---
@mcp.tool()
def destroy_container_repository(repository_id: str, client_mutation_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Schedules a container repository for deletion.

    Args:
        repository_id (str): ID of the container repository.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation DestroyContainerRepository($repositoryId: ContainerRepositoryID!, $clientMutationId: String) {
      destroyContainerRepository(input: { id: $repositoryId, clientMutationId: $clientMutationId }) {
        clientMutationId
        containerRepository {
          id
          name
          status
          path
          location
        }
        errors
      }
    }
    """
    variables: Dict[str, Any] = {
        "repositoryId": repository_id,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.destroyContainerRepositoryTags ---
@mcp.tool()
def destroy_container_repository_tags(
    id: str,
    tag_names: list[str],
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Deletes specified tags from a container repository.

    Args:
        id (str): ID of the container repository.
        tag_names (list[str]): Container repository tag(s) to delete. Total number can't be greater than 20.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation DestroyContainerRepositoryTags($input: DestroyContainerRepositoryTagsInput!) {
      destroyContainerRepositoryTags(input: $input) {
        clientMutationId
        deletedTagNames
        errors
      }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "id": id,
            "tagNames": tag_names,
        }
    }
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.destroyCustomEmoji ---
@mcp.tool()
def destroy_custom_emoji(custom_emoji_id: str, client_mutation_id: Optional[str] = None) -> Dict[str, Any]:
    """Destroys a custom emoji.

    Args:
        custom_emoji_id (str): Global ID of the custom emoji to destroy.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation DestroyCustomEmoji($customEmojiId: CustomEmojiID!, $clientMutationId: String) {
      destroyCustomEmoji(input: { id: $customEmojiId, clientMutationId: $clientMutationId }) {
        clientMutationId
        customEmoji {
          id
          name
          external
          sourceUrl
        }
        errors
      }
    }
    """
    variables = {
        "customEmojiId": custom_emoji_id,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.destroyEpicBoard ---
@mcp.tool()
def destroy_epic_board(id: str, client_mutation_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Destroys an existing epic board.

    Args:
        id (str): Global ID of the board to destroy.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
        mutation destroyEpicBoard($id: BoardsEpicBoardID!, $clientMutationId: String) {
          destroyEpicBoard(input: { id: $id, clientMutationId: $clientMutationId }) {
            clientMutationId
            epicBoard {
              id
              title
              state
              createdAt
              updatedAt
              group {
                fullName
                webUrl
              }
            }
            errors
          }
        }
    """
    variables = {
        "id": id,
        "clientMutationId": client_mutation_id,
    }
    return _graphql_request(query, variables=variables)

# --- Mutation.destroyNote ---
@mcp.tool()
def destroy_note(id: str, client_mutation_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Destroys a note in GitLab.

    Args:
        id (str): Global ID of the note to destroy.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
        mutation destroyNote($id: NoteID!, $clientMutationId: String) {
            destroyNote(input: { id: $id, clientMutationId: $clientMutationId }) {
                clientMutationId
                errors
                note {
                    id
                    body
                    createdAt
                    updatedAt
                    url
                }
            }
        }
    """
    variables = {
        "id": id,
        "clientMutationId": client_mutation_id,
    }
    return _graphql_request(query, variables)

# --- Mutation.destroyPackage ---
@mcp.tool()
def destroy_package(id: str, client_mutation_id: Optional[str] = None) -> Dict[str, Any]:
    """Destroy a GitLab package.

    Args:
        id: ID of the Package.
        client_mutation_id: A unique identifier for the client performing the mutation.
    """
    query = """
    mutation destroyPackage($id: PackagesPackageID!, $clientMutationId: String) {
      destroyPackage(input: { id: $id, clientMutationId: $clientMutationId }) {
        clientMutationId
        errors
      }
    }
    """
    variables: Dict[str, Any] = {
        "id": id,
        "clientMutationId": client_mutation_id,
    }
    return _graphql_request(query, variables)

# --- Mutation.destroyPackageFile ---
@mcp.tool()
def destroy_package_file(
    package_file_id: str,
    client_mutation_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Destroys a package file in GitLab.

    Args:
        package_file_id (str): ID of the Package file.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation DestroyPackageFile($input: DestroyPackageFileInput!) {
      destroyPackageFile(input: $input) {
        clientMutationId
        errors
      }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "id": package_file_id,
        }
    }
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.destroyPackageFiles ---
@mcp.tool()
def destroy_package_files(
    ids: List[List[str]],
    project_path: str,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Destroys package files in a project.

    Args:
        ids (List[List[str]]): IDs of the Package file.
        project_path (str): Project path where the packages cleanup policy is located.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation DestroyPackageFiles($clientMutationId: String, $ids: [[PackagesPackageFileID!]!]!, $projectPath: ID!) {
      destroyPackageFiles(input: {
        clientMutationId: $clientMutationId,
        ids: $ids,
        projectPath: $projectPath
      }) {
        clientMutationId
        errors
      }
    }
    """
    variables: Dict[str, Any] = {
        "ids": ids,
        "projectPath": project_path,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.destroyPackages ---
@mcp.tool()
def destroy_packages(
    ids: List[List[str]],
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Destroys packages in GitLab.

    Args:
        ids: Global IDs of the Packages. Max 20.
        client_mutation_id: A unique identifier for the client performing the mutation.
    """
    query = """
    mutation DestroyPackages($input: DestroyPackagesInput!) {
        destroyPackages(input: $input) {
            clientMutationId
            errors
        }
    }
    """
    variables = {
        "input": {
            "ids": ids,
        }
    }
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.destroySnippet ---
@mcp.tool()
def destroy_snippet(id: str, client_mutation_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Destroys a GitLab snippet.

    Args:
        id: Global ID of the snippet to destroy.
        client_mutation_id: A unique identifier for the client performing the mutation.
    """
    query = """
    mutation DestroySnippet($id: SnippetID!, $clientMutationId: String) {
      destroySnippet(input: { id: $id, clientMutationId: $clientMutationId }) {
        clientMutationId
        errors
        snippet {
          id
          title
          description
          fileName
          webUrl
        }
      }
    }
    """
    variables = {
        "id": id,
        "clientMutationId": client_mutation_id,
    }
    return _graphql_request(query, variables)

# --- Mutation.disableDevopsAdoptionNamespace ---
@mcp.tool()
def disable_devops_adoption_namespace(
    ids: List[str],
    client_mutation_id: Optional[str] = None
) -> Dict[str, Any]:
    """Disables DevOps adoption tracking for one or more namespaces.

    Args:
        ids: One or many IDs of the enabled namespaces to disable.
        client_mutation_id: A unique identifier for the client performing the mutation.
    """
    query = """
    mutation DisableDevopsAdoptionNamespace($input: DisableDevopsAdoptionNamespaceInput!) {
      disableDevopsAdoptionNamespace(input: $input) {
        clientMutationId
        errors
      }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "id": ids,
        }
    }
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.discussionToggleResolve ---
@mcp.tool()
def discussion_toggle_resolve(
    id: str,
    resolve: bool,
    client_mutation_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Toggles the resolved state of a discussion.

    Args:
        id: Global ID of the discussion.
        resolve: Will resolve the discussion when true, and unresolve the discussion when false.
        client_mutation_id: A unique identifier for the client performing the mutation.
    """
    query = """
    mutation DiscussionToggleResolve($id: DiscussionID!, $resolve: Boolean!, $clientMutationId: String) {
      discussionToggleResolve(input: {
        id: $id,
        resolve: $resolve,
        clientMutationId: $clientMutationId
      }) {
        clientMutationId
        discussion {
          id
          resolved
          diffHunk
          notes(first: 10) { # Fetch up to 10 notes for context
            nodes {
              id
              body
              author {
                username
              }
            }
          }
        }
        errors
      }
    }
    """
    variables: Dict[str, Any] = {
        "id": id,
        "resolve": resolve,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.echoCreate ---
@mcp.tool()
def echo_create(
    client_mutation_id: Optional[str] = None,
    errors: Optional[List[List[str]]] = None,
    messages: Optional[List[List[str]]] = None,
) -> Dict[str, Any]:
    """
    A mutation that does not perform any changes, used for testing access.

    Args:
        client_mutation_id: A unique identifier for the client performing the mutation.
        errors: Errors to return to the user.
        messages: Messages to return to the user.
    """
    query = """
    mutation EchoCreate(
      $clientMutationId: String
      $errors: [[String!]]
      $messages: [[String!]]
    ) {
      echoCreate(input: {
        clientMutationId: $clientMutationId
        errors: $errors
        messages: $messages
      }) {
        clientMutationId
        echoes
        errors
      }
    }
    """
    variables: Dict[str, Any] = {}
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id
    if errors is not None:
        variables["errors"] = errors
    if messages is not None:
        variables["messages"] = messages

    return _graphql_request(query, variables)

# --- Mutation.enableDevopsAdoptionNamespace ---
@mcp.tool()
def enable_devops_adoption_namespace(
    namespace_id: str,
    client_mutation_id: Optional[str] = None,
    display_namespace_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Enables DevOps adoption for a given namespace.

    Args:
        namespace_id: The ID of the namespace to enable DevOps adoption for.
        client_mutation_id: A unique identifier for the client performing the mutation.
        display_namespace_id: Display namespace ID.
    """
    query = """
        mutation EnableDevopsAdoptionNamespace(
            $clientMutationId: String,
            $displayNamespaceId: NamespaceID,
            $namespaceId: NamespaceID!
        ) {
            enableDevopsAdoptionNamespace(input: {
                clientMutationId: $clientMutationId,
                displayNamespaceId: $displayNamespaceId,
                namespaceId: $namespaceId
            }) {
                clientMutationId
                enabledNamespace {
                    id
                    name
                    fullPath
                    createdAt
                    updatedAt
                }
                errors
            }
        }
    """
    variables: Dict[str, Any] = {
        "namespaceId": namespace_id,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id
    if display_namespace_id is not None:
        variables["displayNamespaceId"] = display_namespace_id

    return _graphql_request(query, variables)

# --- Mutation.environmentsCanaryIngressUpdate ---
@mcp.tool()
def environments_canary_ingress_update(id: str, weight: int, client_mutation_id: Optional[str] = None) -> Dict[str, Any]:
    """Deprecated: Updates the weight of a Canary Ingress for an environment.

    Args:
        id (str): Global ID of the environment to update.
        weight (int): Weight of the Canary Ingress.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation environmentsCanaryIngressUpdate(
      $clientMutationId: String,
      $id: EnvironmentID!,
      $weight: Int!
    ) {
      environmentsCanaryIngressUpdate(input: {
        clientMutationId: $clientMutationId,
        id: $id,
        weight: $weight
      }) {
        clientMutationId
        errors
      }
    }
    """
    variables = {
        "clientMutationId": client_mutation_id,
        "id": id,
        "weight": weight,
    }
    return _graphql_request(query, variables)

# --- Mutation.epicAddIssue ---
@mcp.tool()
def epic_add_issue(
    group_path: str,
    iid: str,
    issue_iid: str,
    project_path: str,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Adds an existing issue to an epic.

    Args:
        group_path (str): Group the epic to mutate belongs to.
        iid (str): IID of the epic to mutate.
        issue_iid (str): IID of the issue to be added.
        project_path (str): Full path of the project the issue belongs to.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation epicAddIssue(
      $clientMutationId: String,
      $groupPath: ID!,
      $iid: ID!,
      $issueIid: String!,
      $projectPath: ID!
    ) {
      epicAddIssue(input: {
        clientMutationId: $clientMutationId,
        groupPath: $groupPath,
        iid: $iid,
        issueIid: $issueIid,
        projectPath: $projectPath
      }) {
        clientMutationId
        epic {
          id
          title
          iid
          state
          webUrl
          group {
            fullPath
          }
        }
        epicIssue {
          id
          issue {
            id
            iid
            title
            webUrl
          }
          epic {
            id
            iid
            title
            webUrl
          }
        }
        errors
      }
    }
    """
    variables: Dict[str, Any] = {
        "groupPath": group_path,
        "iid": iid,
        "issueIid": issue_iid,
        "projectPath": project_path,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.epicBoardCreate ---
@mcp.tool()
def epic_board_create(
    group_path: str,
    client_mutation_id: Optional[str] = None,
    hide_backlog_list: Optional[bool] = None,
    hide_closed_list: Optional[bool] = None,
    label_ids: Optional[List[str]] = None,
    labels: Optional[List[str]] = None,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Creates a new epic board for a group.

    Args:
        group_path (str): Full path of the group with which the resource is associated.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        hide_backlog_list (Optional[bool]): Whether or not backlog list is hidden.
        hide_closed_list (Optional[bool]): Whether or not closed list is hidden.
        label_ids (Optional[List[str]]): IDs of labels to be added to the board.
        labels (Optional[List[str]]): Labels of the issue.
        name (Optional[str]): Board name.
    """
    query = """
    mutation EpicBoardCreate($input: EpicBoardCreateInput!) {
      epicBoardCreate(input: $input) {
        clientMutationId
        epicBoard {
          id
          name
          hideBacklogList
          hideClosedList
        }
        errors
      }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "groupPath": group_path,
        }
    }
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id
    if hide_backlog_list is not None:
        variables["input"]["hideBacklogList"] = hide_backlog_list
    if hide_closed_list is not None:
        variables["input"]["hideClosedList"] = hide_closed_list
    if label_ids is not None:
        variables["input"]["labelIds"] = label_ids
    if labels is not None:
        variables["input"]["labels"] = labels
    if name is not None:
        variables["input"]["name"] = name

    return _graphql_request(query, variables)

# --- Mutation.epicBoardListCreate ---
@mcp.tool()
def epic_board_list_create(
    board_id: str,
    backlog: Optional[bool] = None,
    client_mutation_id: Optional[str] = None,
    label_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Creates an epic board list.

    Args:
        board_id: Global ID of the issue board to mutate.
        backlog: Create the backlog list.
        client_mutation_id: A unique identifier for the client performing the mutation.
        label_id: Global ID of an existing label.
    """
    query = """
    mutation EpicBoardListCreate($input: EpicBoardListCreateInput!) {
      epicBoardListCreate(input: $input) {
        clientMutationId
        errors
        list {
          id
          title
          listType
          position
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "boardId": board_id,
        }
    }
    if backlog is not None:
        variables["input"]["backlog"] = backlog
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id
    if label_id is not None:
        variables["input"]["labelId"] = label_id

    return _graphql_request(query, variables)

# --- Mutation.epicBoardListDestroy ---
@mcp.tool()
def epic_board_list_destroy(list_id: str, client_mutation_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Destroys an epic board list.

    Args:
        list_id (str): Global ID of the epic board list to destroy.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation EpicBoardListDestroy($listId: BoardsEpicListID!, $clientMutationId: String) {
      epicBoardListDestroy(input: { listId: $listId, clientMutationId: $clientMutationId }) {
        clientMutationId
        errors
        list {
          id
          title
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "listId": list_id,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.epicBoardUpdate ---
@mcp.tool()
def epic_board_update(
    id: str,
    client_mutation_id: Optional[str] = None,
    hide_backlog_list: Optional[bool] = None,
    hide_closed_list: Optional[bool] = None,
    label_ids: Optional[List[List[str]]] = None,
    labels: Optional[List[List[str]]] = None,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Updates an existing epic board in GitLab.

    Args:
        id: Epic board global ID.
        client_mutation_id: A unique identifier for the client performing the mutation.
        hide_backlog_list: Whether or not backlog list is hidden.
        hide_closed_list: Whether or not closed list is hidden.
        label_ids: IDs of labels to be added to the board (list of lists of IDs).
        labels: Labels of the issue (list of lists of strings).
        name: Board name.
    """
    query = """
    mutation EpicBoardUpdate($input: EpicBoardUpdateInput!) {
      epicBoardUpdate(input: $input) {
        clientMutationId
        epicBoard {
          id
          name
          hideBacklogList
          hideClosedList
          labels {
            nodes {
              id
              title
              color
              description
            }
          }
        }
        errors
      }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "id": id,
        }
    }

    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id
    if hide_backlog_list is not None:
        variables["input"]["hideBacklogList"] = hide_backlog_list
    if hide_closed_list is not None:
        variables["input"]["hideClosedList"] = hide_closed_list
    if label_ids is not None:
        variables["input"]["labelIds"] = label_ids
    if labels is not None:
        variables["input"]["labels"] = labels
    if name is not None:
        variables["input"]["name"] = name

    return _graphql_request(query, variables)

# --- Mutation.epicMoveList ---
@mcp.tool()
def epic_move_list(
    board_id: str,
    epic_id: str,
    to_list_id: str,
    client_mutation_id: Optional[str] = None,
    from_list_id: Optional[str] = None,
    move_after_id: Optional[str] = None,
    move_before_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Moves an epic between or within board lists.

    Args:
        board_id (str): Global ID of the board that the epic is in.
        epic_id (str): ID of the epic to mutate.
        to_list_id (str): ID of the list the epic will be in after mutation.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        from_list_id (Optional[str]): ID of the board list that the epic will be moved from.
                                      Required if moving between lists.
        move_after_id (Optional[str]): ID of epic that should be placed after the current epic.
        move_before_id (Optional[str]): ID of epic that should be placed before the current epic.
    """
    query = """
    mutation EpicMoveList(
      $boardId: BoardsEpicBoardID!,
      $epicId: EpicID!,
      $toListId: BoardsEpicListID!,
      $clientMutationId: String,
      $fromListId: BoardsEpicListID,
      $moveAfterId: EpicID,
      $moveBeforeId: EpicID
    ) {
      epicMoveList(input: {
        boardId: $boardId,
        epicId: $epicId,
        toListId: $toListId,
        clientMutationId: $clientMutationId,
        fromListId: $fromListId,
        moveAfterId: $moveAfterId,
        moveBeforeId: $moveBeforeId
      }) {
        clientMutationId
        epic {
          id
          iid
          title
          group {
            id
            fullPath
          }
        }
        errors
      }
    }
    """
    variables: Dict[str, Any] = {
        "boardId": board_id,
        "epicId": epic_id,
        "toListId": to_list_id,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id
    if from_list_id is not None:
        variables["fromListId"] = from_list_id
    if move_after_id is not None:
        variables["moveAfterId"] = move_after_id
    if move_before_id is not None:
        variables["moveBeforeId"] = move_before_id

    return _graphql_request(query, variables)

# --- Mutation.epicSetSubscription ---
@mcp.tool()
def epic_set_subscription(
    group_path: str,
    iid: str,
    subscribed_state: bool,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Sets the subscription state for an epic.

    Args:
        group_path (str): Group the epic to mutate belongs to.
        iid (str): IID of the epic to mutate.
        subscribed_state (bool): Desired state of the subscription.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation EpicSetSubscription($input: EpicSetSubscriptionInput!) {
      epicSetSubscription(input: $input) {
        clientMutationId
        epic {
          id
          iid
          title
          state
          subscribed
        }
        errors
      }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "groupPath": group_path,
            "iid": iid,
            "subscribedState": subscribed_state,
        }
    }
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.epicTreeReorder ---
@mcp.tool()
def epic_tree_reorder(
    base_epic_id: str,
    moved: Dict[str, Any],
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Reorders epics in an epic tree.

    Args:
        base_epic_id (str): ID of the base epic of the tree.
        moved (Dict[str, Any]): Parameters for updating the tree positions.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation EpicTreeReorder($baseEpicId: EpicID!, $moved: EpicTreeNodeFieldsInputType!, $clientMutationId: String) {
      epicTreeReorder(input: {
        baseEpicId: $baseEpicId,
        moved: $moved,
        clientMutationId: $clientMutationId
      }) {
        clientMutationId
        errors
      }
    }
    """
    variables: Dict[str, Any] = {
        "baseEpicId": base_epic_id,
        "moved": moved,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.escalationPolicyCreate ---
@mcp.tool()
def escalation_policy_create(
    name: str,
    project_path: str,
    rules: List[List[Dict[str, Any]]],
    client_mutation_id: Optional[str] = None,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Creates a new escalation policy.

    Args:
        name (str): Name of the escalation policy.
        project_path (str): Project to create the escalation policy for.
        rules (List[List[Dict[str, Any]]]): Steps of the escalation policy.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        description (Optional[str]): Description of the escalation policy.
    """
    query = """
    mutation EscalationPolicyCreate($input: EscalationPolicyCreateInput!) {
      escalationPolicyCreate(input: $input) {
        clientMutationId
        errors
        escalationPolicy {
          id
          name
          description
          rules {
            id
            elapsedTimeSeconds
            oncallSchedule {
              id
              name
            }
          }
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "name": name,
            "projectPath": project_path,
            "rules": rules,
        }
    }
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id
    if description is not None:
        variables["input"]["description"] = description

    return _graphql_request(query, variables)

# --- Mutation.escalationPolicyDestroy ---
@mcp.tool()
def escalation_policy_destroy(
    id: str,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Destroys an existing escalation policy.

    Args:
        id (str): Escalation policy internal ID to remove.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation escalationPolicyDestroy($id: IncidentManagementEscalationPolicyID!, $clientMutationId: String) {
      escalationPolicyDestroy(input: {
        id: $id,
        clientMutationId: $clientMutationId
      }) {
        clientMutationId
        errors
        escalationPolicy {
          id
          name
          description
          rulesCount
          active
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "id": id,
        "clientMutationId": client_mutation_id,
    }
    return _graphql_request(query, variables)

# --- Mutation.escalationPolicyUpdate ---
@mcp.tool()
def escalation_policy_update(
    policy_id: str,
    client_mutation_id: Optional[str] = None,
    description: Optional[str] = None,
    name: Optional[str] = None,
    rules: Optional[List[List[Dict[str, Any]]]] = None,
) -> Dict[str, Any]:
    """Updates an existing escalation policy.

    Args:
        policy_id (str): ID of the on-call schedule to create the on-call rotation in.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        description (Optional[str]): Description of the escalation policy.
        name (Optional[str]): Name of the escalation policy.
        rules (Optional[List[List[Dict[str, Any]]]]): Steps of the escalation policy.
    """
    query = """
    mutation escalationPolicyUpdate(
      $clientMutationId: String
      $description: String
      $id: IncidentManagementEscalationPolicyID!
      $name: String
      $rules: [[EscalationRuleInput!]]
    ) {
      escalationPolicyUpdate(input: {
        clientMutationId: $clientMutationId
        description: $description
        id: $id
        name: $name
        rules: $rules
      }) {
        clientMutationId
        errors
        escalationPolicy {
          id
          name
          description
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "id": policy_id,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id
    if description is not None:
        variables["description"] = description
    if name is not None:
        variables["name"] = name
    if rules is not None:
        variables["rules"] = rules

    return _graphql_request(query, variables)

# --- Mutation.exportRequirements ---
@mcp.tool()
def export_requirements(
    project_path: str,
    author_username: Optional[List[str]] = None,
    client_mutation_id: Optional[str] = None,
    search: Optional[str] = None,
    selected_fields: Optional[List[str]] = None,
    sort: Optional[str] = None,
    state: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Exports requirements for a given project.

    Args:
        project_path (str): Full project path the requirements are associated with.
        author_username (Optional[List[str]]): Filter requirements by author username.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        search (Optional[str]): Search query for requirement title.
        selected_fields (Optional[List[str]]): List of selected requirements fields to be exported.
        sort (Optional[str]): List requirements by sort order.
        state (Optional[str]): Filter requirements by state.
    """
    query = """
    mutation ExportRequirements(
        $authorUsername: [String!],
        $clientMutationId: String,
        $projectPath: ID!,
        $search: String,
        $selectedFields: [String!],
        $sort: Sort,
        $state: RequirementState
    ) {
        exportRequirements(input: {
            authorUsername: $authorUsername,
            clientMutationId: $clientMutationId,
            projectPath: $projectPath,
            search: $search,
            selectedFields: $selectedFields,
            sort: $sort,
            state: $state
        }) {
            clientMutationId
            errors
        }
    }
    """
    variables: Dict[str, Any] = {
        "authorUsername": author_username,
        "clientMutationId": client_mutation_id,
        "projectPath": project_path,
        "search": search,
        "selectedFields": selected_fields,
        "sort": sort,
        "state": state,
    }
    # Remove None values to avoid sending null for optional GraphQL arguments
    variables = {k: v for k, v in variables.items() if v is not None}

    return _graphql_request(query, variables)

# --- Mutation.externalAuditEventDestinationCreate ---
@mcp.tool()
def external_audit_event_destination_create(
    destination_url: str,
    group_path: str,
    client_mutation_id: Optional[str] = None,
    verification_token: Optional[str] = None
) -> Dict[str, Any]:
    """Creates an external audit event destination for a group.

    Args:
        destination_url (str): Destination URL.
        group_path (str): Group path.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        verification_token (Optional[str]): Verification token.
    """
    query = """
    mutation ExternalAuditEventDestinationCreate(
      $destinationUrl: String!
      $groupPath: ID!
      $clientMutationId: String
      $verificationToken: String
    ) {
      externalAuditEventDestinationCreate(input: {
        destinationUrl: $destinationUrl
        groupPath: $groupPath
        clientMutationId: $clientMutationId
        verificationToken: $verificationToken
      }) {
        clientMutationId
        errors
        externalAuditEventDestination {
          id
          destinationUrl
          verificationToken
          group {
            id
            fullPath
          }
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "destinationUrl": destination_url,
        "groupPath": group_path,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id
    if verification_token is not None:
        variables["verificationToken"] = verification_token

    return _graphql_request(query, variables)

# --- Mutation.externalAuditEventDestinationDestroy ---
@mcp.tool()
def external_audit_event_destination_destroy(id: str, client_mutation_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Destroys an external audit event destination.

    Args:
        id (str): ID of external audit event destination to destroy.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation ExternalAuditEventDestinationDestroy($id: AuditEventsExternalAuditEventDestinationID!, $clientMutationId: String) {
      externalAuditEventDestinationDestroy(input: { id: $id, clientMutationId: $clientMutationId }) {
        clientMutationId
        errors
      }
    }
    """
    variables: Dict[str, Any] = {"id": id}
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.externalAuditEventDestinationUpdate ---
@mcp.tool()
def external_audit_event_destination_update(
    id: str,
    client_mutation_id: Optional[str] = None,
    destination_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Updates an external audit event destination.

    Args:
        id (str): ID of external audit event destination to update.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        destination_url (Optional[str]): Destination URL to change.
    """
    query = """
    mutation ExternalAuditEventDestinationUpdate($input: ExternalAuditEventDestinationUpdateInput!) {
      externalAuditEventDestinationUpdate(input: $input) {
        clientMutationId
        errors
        externalAuditEventDestination {
          id
          destinationUrl
        }
      }
    }
    """
    variables: Dict[str, Any] = {"input": {"id": id}}
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id
    if destination_url is not None:
        variables["input"]["destinationUrl"] = destination_url

    return _graphql_request(query, variables)

# --- Mutation.gitlabSubscriptionActivate ---
@mcp.tool()
def gitlab_subscription_activate(
    activation_code: str,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Activates a GitLab subscription using a provided activation code.

    Args:
        activation_code (str): Activation code received after purchasing a GitLab subscription.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation GitlabSubscriptionActivate($activationCode: String!, $clientMutationId: String) {
      gitlabSubscriptionActivate(input: {
        activationCode: $activationCode,
        clientMutationId: $clientMutationId
      }) {
        clientMutationId
        errors
        futureSubscriptions {
          startsAt
          expiresAt
          plan {
            name
          }
        }
        license {
          id
          startsAt
          expiresAt
          userName
          userCount
          plan {
            name
          }
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "activationCode": activation_code,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.groupUpdate ---
@mcp.tool()
def group_update(
    full_path: str,
    shared_runners_setting: str,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Updates an existing group in GitLab.

    Args:
        full_path: Full path of the group that will be updated.
        shared_runners_setting: Shared runners availability for the namespace and its descendants.
        client_mutation_id: A unique identifier for the client performing the mutation.
    """
    query = """
    mutation groupUpdateMutation(
      $fullPath: ID!,
      $sharedRunnersSetting: SharedRunnersSetting!,
      $clientMutationId: String
    ) {
      groupUpdate(input: {
        fullPath: $fullPath,
        sharedRunnersSetting: $sharedRunnersSetting,
        clientMutationId: $clientMutationId
      }) {
        clientMutationId
        errors
        group {
          id
          fullPath
          name
          description
          sharedRunnersSetting
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "fullPath": full_path,
        "sharedRunnersSetting": shared_runners_setting,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.httpIntegrationCreate ---
@mcp.tool()
def http_integration_create(
    active: bool,
    name: str,
    project_path: str,
    client_mutation_id: Optional[str] = None,
    payload_attribute_mappings: Optional[List[Dict[str, Any]]] = None,
    payload_example: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Creates a new HTTP integration for a project.

    Args:
        active: Whether the integration is receiving alerts.
        name: Name of the integration.
        project_path: Project to create the integration in.
        client_mutation_id: A unique identifier for the client performing the mutation.
        payload_attribute_mappings: Custom mapping of GitLab alert attributes to fields from the payload example.
        payload_example: Example of an alert payload.
    """
    query = """
    mutation HttpIntegrationCreate($input: HttpIntegrationCreateInput!) {
      httpIntegrationCreate(input: $input) {
        clientMutationId
        errors
        integration {
          id
          name
          active
          url
          token
          payloadAttributeMappings {
            fieldName
            path
            type
            label
          }
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "active": active,
            "name": name,
            "projectPath": project_path,
        }
    }
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id
    if payload_attribute_mappings is not None:
        variables["input"]["payloadAttributeMappings"] = payload_attribute_mappings
    if payload_example is not None:
        variables["input"]["payloadExample"] = payload_example

    return _graphql_request(query, variables)

# --- Mutation.httpIntegrationDestroy ---
@mcp.tool()
def http_integration_destroy(id: str, client_mutation_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Destroys an existing HTTP integration for alert management.

    Args:
        id (str): ID of the integration to remove.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation HttpIntegrationDestroy($id: AlertManagementHttpIntegrationID!, $clientMutationId: String) {
        httpIntegrationDestroy(input: { id: $id, clientMutationId: $clientMutationId }) {
            clientMutationId
            errors
            integration {
                id
                name
                type
                url
                active
            }
        }
    }
    """
    variables: Dict[str, Any] = {
        "id": id,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.httpIntegrationResetToken ---
@mcp.tool()
def http_integration_reset_token(id: str, client_mutation_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Resets the token for a GitLab HTTP integration.

    Args:
        id (str): ID of the integration to mutate.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
        mutation HttpIntegrationResetToken($input: HttpIntegrationResetTokenInput!) {
            httpIntegrationResetToken(input: $input) {
                clientMutationId
                errors
                integration {
                    id
                    name
                    type
                    url
                    active
                }
            }
        }
    """
    variables = {
        "input": {
            "id": id
        }
    }
    if client_mutation_id:
        variables["input"]["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.httpIntegrationUpdate ---
@mcp.tool()
def http_integration_update(
    id: str,
    active: Optional[bool] = None,
    client_mutation_id: Optional[str] = None,
    name: Optional[str] = None,
    payload_attribute_mappings: Optional[List[Dict[str, Any]]] = None,
    payload_example: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Updates an existing HTTP integration for alert management.

    Args:
        id (str): ID of the integration to mutate.
        active (Optional[bool]): Whether the integration is receiving alerts.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        name (Optional[str]): Name of the integration.
        payload_attribute_mappings (Optional[List[Dict[str, Any]]]): Custom mapping of GitLab alert attributes to fields from the payload example.
        payload_example (Optional[str]): Example of an alert payload.
    """
    query = """
    mutation HttpIntegrationUpdate(
      $id: AlertManagementHttpIntegrationID!
      $active: Boolean
      $clientMutationId: String
      $name: String
      $payloadAttributeMappings: [AlertManagementPayloadAlertFieldInput!]
      $payloadExample: JsonString
    ) {
      httpIntegrationUpdate(input: {
        id: $id
        active: $active
        clientMutationId: $clientMutationId
        name: $name
        payloadAttributeMappings: $payloadAttributeMappings
        payloadExample: $payloadExample
      }) {
        clientMutationId
        errors
        integration {
          id
          name
          active
          type
          url
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "id": id,
        "active": active,
        "clientMutationId": client_mutation_id,
        "name": name,
        "payloadAttributeMappings": payload_attribute_mappings,
        "payloadExample": payload_example,
    }
    # Remove None values to avoid sending nulls for optional fields
    variables = {k: v for k, v in variables.items() if v is not None}
    return _graphql_request(query, variables)

# --- Mutation.issuableResourceLinkCreate ---
@mcp.tool()
def issuable_resource_link_create(
    id: str,
    link: str,
    client_mutation_id: Optional[str] = None,
    link_text: Optional[str] = None,
    link_type: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Creates a new resource link for an issuable (e.g., an incident).

    Args:
        id (str): Incident ID to associate the resource link with.
        link (str): Link of the resource.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        link_text (Optional[str]): Link text of the resource.
        link_type (Optional[str]): Link type of the resource.
    """
    query = """
    mutation IssuableResourceLinkCreate(
      $clientMutationId: String,
      $id: IssueID!,
      $link: String!,
      $linkText: String,
      $linkType: IssuableResourceLinkType
    ) {
      issuableResourceLinkCreate(input: {
        clientMutationId: $clientMutationId,
        id: $id,
        link: $link,
        linkText: $linkText,
        linkType: $linkType
      }) {
        clientMutationId
        errors
        issuableResourceLink {
          id
          link
          linkText
          linkType
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "id": id,
        "link": link,
        "clientMutationId": client_mutation_id,
        "linkText": link_text,
        "linkType": link_type,
    }
    return _graphql_request(query, variables)

# --- Mutation.issuableResourceLinkDestroy ---
@mcp.tool()
def issuable_resource_link_destroy(
    id: str,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Destroys an existing issuable resource link.

    Args:
        id (str): Issuable resource link ID to remove.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation IssuableResourceLinkDestroy(
      $id: IncidentManagementIssuableResourceLinkID!
      $clientMutationId: String
    ) {
      issuableResourceLinkDestroy(input: {
        id: $id
        clientMutationId: $clientMutationId
      }) {
        clientMutationId
        errors
        issuableResourceLink {
          id
          link
          linkType
          title
          resource
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "id": id,
        "clientMutationId": client_mutation_id,
    }
    return _graphql_request(query, variables)

# --- Mutation.issueLinkAlerts ---
@mcp.tool()
def issue_link_alerts(
    alert_references: List[List[str]],
    iid: str,
    project_path: str,
    client_mutation_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Links alerts to an existing GitLab issue (incident).

    Args:
        alert_references: Alerts references to be linked to the incident.
        iid: IID of the issue to mutate.
        project_path: Project the issue to mutate is in (e.g., "group/project").
        client_mutation_id: A unique identifier for the client performing the mutation.
    """
    query = """
        mutation IssueLinkAlerts(
            $alertReferences: [[String!]!]!,
            $clientMutationId: String,
            $iid: String!,
            $projectPath: ID!
        ) {
            issueLinkAlerts(input: {
                alertReferences: $alertReferences,
                clientMutationId: $clientMutationId,
                iid: $iid,
                projectPath: $projectPath
            }) {
                clientMutationId
                errors
                issue {
                    id
                    iid
                    title
                    state
                    webUrl
                    createdAt
                    updatedAt
                    descriptionHtml
                }
            }
        }
    """
    variables: Dict[str, Any] = {
        "alertReferences": alert_references,
        "iid": iid,
        "projectPath": project_path,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables=variables)

# --- Mutation.issueMove ---
@mcp.tool()
def issue_move(
    iid: str,
    project_path: str,
    target_project_path: str,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Moves an issue to a new project.

    Args:
        iid (str): IID of the issue to mutate.
        project_path (str): Project the issue to mutate is in.
        target_project_path (str): Project to move the issue to.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation issueMoveMutation(
        $clientMutationId: String,
        $iid: String!,
        $projectPath: ID!,
        $targetProjectPath: ID!
    ) {
        issueMove(input: {
            clientMutationId: $clientMutationId,
            iid: $iid,
            projectPath: $projectPath,
            targetProjectPath: $targetProjectPath
        }) {
            clientMutationId
            errors
            issue {
                id
                iid
                title
                webUrl
                state
                createdAt
                updatedAt
                dueDate
                confidential
                discussionLocked
                relativePosition
            }
        }
    }
    """
    variables = {
        "iid": iid,
        "projectPath": project_path,
        "targetProjectPath": target_project_path,
        "clientMutationId": client_mutation_id,
    }
    # Remove None values from variables to avoid sending null for optional fields
    variables = {k: v for k, v in variables.items() if v is not None}

    return _graphql_request(query, variables)

# --- Mutation.issueMoveList ---
@mcp.tool()
def issue_move_list(
    board_id: str,
    iid: str,
    project_path: str,
    client_mutation_id: Optional[str] = None,
    epic_id: Optional[str] = None,
    from_list_id: Optional[str] = None,
    move_after_id: Optional[str] = None,
    move_before_id: Optional[str] = None,
    position_in_list: Optional[int] = None,
    to_list_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Move an issue to a new position within or between board lists.

    Args:
        board_id (str): Global ID of the board that the issue is in.
        iid (str): IID of the issue to mutate.
        project_path (str): Project the issue to mutate is in.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        epic_id (Optional[str]): ID of the parent epic. NULL when removing the association.
        from_list_id (Optional[str]): ID of the board list that the issue will be moved from.
        move_after_id (Optional[str]): ID of issue that should be placed after the current issue.
        move_before_id (Optional[str]): ID of issue that should be placed before the current issue.
        position_in_list (Optional[int]): Position of issue within the board list.
                                         Use -1 to move to the end of the list.
        to_list_id (Optional[str]): ID of the board list that the issue will be moved to.
    """
    query = """
    mutation IssueMoveList($input: IssueMoveListInput!) {
        issueMoveList(input: $input) {
            clientMutationId
            errors
            issue {
                id
                iid
                title
                state
                webUrl
            }
        }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "boardId": board_id,
            "iid": iid,
            "projectPath": project_path,
        }
    }
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id
    if epic_id is not None:
        variables["input"]["epicId"] = epic_id
    if from_list_id is not None:
        variables["input"]["fromListId"] = from_list_id
    if move_after_id is not None:
        variables["input"]["moveAfterId"] = move_after_id
    if move_before_id is not None:
        variables["input"]["moveBeforeId"] = move_before_id
    if position_in_list is not None:
        variables["input"]["positionInList"] = position_in_list
    if to_list_id is not None:
        variables["input"]["toListId"] = to_list_id

    return _graphql_request(query, variables)

# --- Mutation.issueSetAssignees ---
@mcp.tool()
def issue_set_assignees(
    project_path: str,
    iid: str,
    assignee_usernames: List[List[str]],
    operation_mode: Optional[str] = None,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Sets or modifies assignees for a GitLab issue.

    Args:
        project_path (str): Project the issue to mutate is in (e.g., "group/project").
        iid (str): IID of the issue to mutate.
        assignee_usernames (List[List[str]]): Usernames to assign to the resource.
        operation_mode (Optional[str]): Operation to perform (e.g., "REPLACE", "APPEND", "REMOVE"). Defaults to REPLACE.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation IssueSetAssignees($projectPath: ID!, $iid: String!, $assigneeUsernames: [[String!]!]!, $operationMode: MutationOperationMode, $clientMutationId: String) {
      issueSetAssignees(input: {
        projectPath: $projectPath,
        iid: $iid,
        assigneeUsernames: $assigneeUsernames,
        operationMode: $operationMode,
        clientMutationId: $clientMutationId
      }) {
        clientMutationId
        errors
        issue {
          id
          iid
          title
          state
          webUrl
          assignees {
            nodes {
              username
              name
            }
          }
        }
      }
    }
    """
    variables = {
        "projectPath": project_path,
        "iid": iid,
        "assigneeUsernames": assignee_usernames,
    }
    if operation_mode is not None:
        variables["operationMode"] = operation_mode
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.issueSetConfidential ---
@mcp.tool()
def issue_set_confidential(
    confidential: bool,
    iid: str,
    project_path: str,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Sets an issue as confidential or not confidential.

    Args:
        confidential (bool): Whether or not to set the issue as confidential.
        iid (str): IID of the issue to mutate.
        project_path (str): Project the issue to mutate is in.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation IssueSetConfidential(
        $clientMutationId: String,
        $confidential: Boolean!,
        $iid: String!,
        $projectPath: ID!
    ) {
        issueSetConfidential(input: {
            clientMutationId: $clientMutationId,
            confidential: $confidential,
            iid: $iid,
            projectPath: $projectPath
        }) {
            clientMutationId
            errors
            issue {
                id
                iid
                title
                confidential
                webUrl
                state
            }
        }
    }
    """
    variables = {
        "confidential": confidential,
        "iid": iid,
        "projectPath": project_path,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.issueSetCrmContacts ---
@mcp.tool()
def issue_set_crm_contacts(
    contact_ids: List[str],
    iid: str,
    project_path: str,
    client_mutation_id: Optional[str] = None,
    operation_mode: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Set CRM contacts for a GitLab issue.

    Args:
        contact_ids: Customer relations contact IDs to set. Replaces existing contacts by default.
        iid: IID of the issue to mutate.
        project_path: Project the issue to mutate is in.
        client_mutation_id: A unique identifier for the client performing the mutation.
        operation_mode: Changes the operation mode. Defaults to REPLACE.
    """
    query = """
    mutation IssueSetCrmContacts(
      $clientMutationId: String,
      $contactIds: [CustomerRelationsContactID!]!,
      $iid: String!,
      $operationMode: MutationOperationMode,
      $projectPath: ID!
    ) {
      issueSetCrmContacts(input: {
        clientMutationId: $clientMutationId,
        contactIds: $contactIds,
        iid: $iid,
        operationMode: $operationMode,
        projectPath: $projectPath
      }) {
        clientMutationId
        errors
        issue {
          id
          iid
          title
          webUrl
          createdAt
          updatedAt
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "contactIds": contact_ids,
        "iid": iid,
        "projectPath": project_path,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id
    if operation_mode is not None:
        variables["operationMode"] = operation_mode

    return _graphql_request(query, variables)

# --- Mutation.issueSetDueDate ---
@mcp.tool()
def issue_set_due_date(
    iid: str,
    project_path: str,
    due_date: Optional[str] = None,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Sets or removes the due date for an issue.

    Args:
        iid (str): IID of the issue to mutate.
        project_path (str): Project the issue to mutate is in.
        due_date (Optional[str]): Desired due date for the issue. Due date is removed if null.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation IssueSetDueDate(
        $iid: String!,
        $projectPath: ID!,
        $dueDate: Time,
        $clientMutationId: String
    ) {
        issueSetDueDate(input: {
            iid: $iid,
            projectPath: $projectPath,
            dueDate: $dueDate,
            clientMutationId: $clientMutationId
        }) {
            clientMutationId
            errors
            issue {
                id
                iid
                title
                dueDate
                state
                webUrl
            }
        }
    }
    """
    variables = {
        "iid": iid,
        "projectPath": project_path,
        "dueDate": due_date,
        "clientMutationId": client_mutation_id,
    }
    return _graphql_request(query, variables)

# --- Mutation.issueSetEpic ---
@mcp.tool()
def issue_set_epic(
    iid: str,
    project_path: str,
    epic_id: Optional[str] = None,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Sets or unsets an epic for an issue.

    Args:
        iid (str): IID of the issue to mutate.
        project_path (str): Project the issue to mutate is in.
        epic_id (Optional[str]): Global ID of the epic to be assigned to the issue, epic will be removed if absent or set to null.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation IssueSetEpic($input: IssueSetEpicInput!) {
      issueSetEpic(input: $input) {
        clientMutationId
        errors
        issue {
          id
          iid
          title
          webUrl
          epic {
            id
            title
            webUrl
          }
        }
      }
    }
    """
    variables = {
        "input": {
            "iid": iid,
            "projectPath": project_path,
        }
    }
    if epic_id is not None:
        variables["input"]["epicId"] = epic_id
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.issueSetEscalationPolicy ---
@mcp.tool()
def issue_set_escalation_policy(
    iid: str,
    project_path: str,
    escalation_policy_id: Optional[str] = None,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Sets or removes an escalation policy for a GitLab issue.

    Args:
        iid (str): IID of the issue to mutate.
        project_path (str): Project the issue to mutate is in.
        escalation_policy_id (Optional[str]): Global ID of the escalation policy to assign.
                                                Policy is removed if absent or null.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    variables: Dict[str, Any] = {
        "iid": iid,
        "projectPath": project_path,
    }
    input_fields: List[str] = [
        "iid: $iid",
        "projectPath: $projectPath",
    ]
    if escalation_policy_id is not None:
        variables["escalationPolicyId"] = escalation_policy_id
        input_fields.append("escalationPolicyId: $escalationPolicyId")
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id
        input_fields.append("clientMutationId: $clientMutationId")

    var_definitions: List[str] = [
        "$iid: String!",
        "$projectPath: ID!",
    ]
    if "escalationPolicyId" in variables:
        var_definitions.append("$escalationPolicyId: IncidentManagementEscalationPolicyID")
    if "clientMutationId" in variables:
        var_definitions.append("$clientMutationId: String")

    query = f"""
    mutation issueSetEscalationPolicy({"(" + ", ".join(var_definitions) + ")" if var_definitions else ""}) {{
      issueSetEscalationPolicy(input: {{ {" ".join(input_fields)} }}) {{
        clientMutationId
        errors
        issue {{
          id
          iid
          title
          webUrl
          escalationPolicy {{
            id
            name
          }}
        }}
      }}
    }}
    """
    return _graphql_request(query, variables)

# --- Mutation.issueSetEscalationStatus ---
from typing import Dict, Any, Optional

@mcp.tool()
def issue_set_escalation_status(
    iid: str,
    project_path: str,
    status: str,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Set the escalation status of a GitLab issue.

    Args:
        iid: IID of the issue to mutate.
        project_path: Project the issue to mutate is in.
        status: The escalation status to set (e.g., "ON_CALL", "RESOLVED").
        client_mutation_id: A unique identifier for the client performing the mutation.
    """
    query = """
    mutation IssueSetEscalationStatus($input: IssueSetEscalationStatusInput!) {
      issueSetEscalationStatus(input: $input) {
        clientMutationId
        errors
        issue {
          id
          iid
          title
          webUrl
          state
          escalationStatus
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "iid": iid,
            "projectPath": project_path,
            "status": status,
        }
    }
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.issueSetIteration ---
@mcp.tool()
def issue_set_iteration(
    iid: str,
    project_path: str,
    iteration_id: Optional[str] = None,
    client_mutation_id: Optional[str] = None
) -> Dict[str, Any]:
    """Sets the iteration for a GitLab issue.

    Args:
        iid (str): IID of the issue to mutate.
        project_path (str): Project the issue to mutate is in.
        iteration_id (Optional[str]): Iteration to assign to the issue.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation IssueSetIteration($iid: String!, $projectPath: ID!, $iterationId: IterationID, $clientMutationId: String) {
      issueSetIteration(input: {
        iid: $iid,
        projectPath: $projectPath,
        iterationId: $iterationId,
        clientMutationId: $clientMutationId
      }) {
        clientMutationId
        errors
        issue {
          id
          title
          webUrl
          iteration {
            id
            title
            startDate
            dueDate
          }
        }
      }
    }
    """
    variables = {
        "iid": iid,
        "projectPath": project_path,
        "iterationId": iteration_id,
        "clientMutationId": client_mutation_id,
    }
    return _graphql_request(query, variables)

# --- Mutation.issueSetLocked ---
@mcp.tool()
def issue_set_locked(
    iid: str,
    locked: bool,
    project_path: str,
    client_mutation_id: Optional[str] = None
) -> Dict[str, Any]:
    """Locks or unlocks discussion on a GitLab issue.

    Args:
        iid: IID of the issue to mutate.
        locked: Whether or not to lock discussion on the issue.
        project_path: Project the issue to mutate is in.
        client_mutation_id: A unique identifier for the client performing the mutation.
    """
    query = """
        mutation IssueSetLockedMutation(
            $iid: String!,
            $locked: Boolean!,
            $projectPath: ID!,
            $clientMutationId: String
        ) {
            issueSetLocked(input: {
                iid: $iid,
                locked: $locked,
                projectPath: $projectPath,
                clientMutationId: $clientMutationId
            }) {
                clientMutationId
                errors
                issue {
                    id
                    title
                    locked
                    state
                    webUrl
                    createdAt
                    updatedAt
                }
            }
        }
    """
    variables: Dict[str, Any] = {
        "iid": iid,
        "locked": locked,
        "projectPath": project_path,
        "clientMutationId": client_mutation_id,
    }
    return _graphql_request(query, variables)

# --- Mutation.issueSetSeverity ---
@mcp.tool()
def issue_set_severity(
    iid: str,
    project_path: str,
    severity: str,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Sets the severity level of an issue.

    Args:
        iid (str): IID of the issue to mutate.
        project_path (str): Project the issue to mutate is in.
        severity (str): Set the incident severity level.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation IssueSetSeverity($input: IssueSetSeverityInput!) {
      issueSetSeverity(input: $input) {
        clientMutationId
        errors
        issue {
          id
          iid
          title
          webUrl
          severity
          state
          createdAt
          updatedAt
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "iid": iid,
            "projectPath": project_path,
            "severity": severity,
        }
    }
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.issueSetSubscription ---
@mcp.tool()
def issue_set_subscription(
    iid: str,
    project_path: str,
    subscribed_state: bool,
    client_mutation_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Sets the subscription state for an issue.

    Args:
        iid (str): IID of the issue to mutate.
        project_path (str): Project the issue to mutate is in.
        subscribed_state (bool): Desired state of the subscription.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation IssueSetSubscription($input: IssueSetSubscriptionInput!) {
      issueSetSubscription(input: $input) {
        clientMutationId
        errors
        issue {
          id
          iid
          title
          state
          subscribed
          webUrl
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "iid": iid,
            "projectPath": project_path,
            "subscribedState": subscribed_state,
        }
    }
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.issueSetWeight ---
@mcp.tool()
def issue_set_weight(
    iid: str,
    project_path: str,
    client_mutation_id: Optional[str] = None,
    weight: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Sets the weight of a GitLab issue.

    Args:
        iid: IID of the issue to mutate.
        project_path: Project the issue to mutate is in.
        client_mutation_id: A unique identifier for the client performing the mutation.
        weight: The desired weight for the issue. If set to null, weight is removed.
    """
    variables: Dict[str, Any] = {
        "input": {
            "iid": iid,
            "projectPath": project_path,
        }
    }
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id
    if weight is not None:
        variables["input"]["weight"] = weight

    query = """
        mutation IssueSetWeight($input: IssueSetWeightInput!) {
            issueSetWeight(input: $input) {
                clientMutationId
                errors
                issue {
                    id
                    iid
                    title
                    description
                    weight
                    webUrl
                    state
                }
            }
        }
    """
    return _graphql_request(query, variables)

# --- Mutation.issueUnlinkAlert ---
@mcp.tool()
def issue_unlink_alert(
    alert_id: str,
    iid: str,
    project_path: str,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Unlinks an alert from an existing issue.

    Args:
        alert_id (str): Global ID of the alert to unlink from the incident.
        iid (str): IID of the issue to mutate.
        project_path (str): Project the issue to mutate is in.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation IssueUnlinkAlert($alertId: AlertManagementAlertID!, $iid: String!, $projectPath: ID!, $clientMutationId: String) {
      issueUnlinkAlert(input: {
        alertId: $alertId,
        iid: $iid,
        projectPath: $projectPath,
        clientMutationId: $clientMutationId
      }) {
        clientMutationId
        errors
        issue {
          id
          iid
          title
          webUrl
          state
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "alertId": alert_id,
        "iid": iid,
        "projectPath": project_path,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.iterationCadenceCreate ---
@mcp.tool()
def iteration_cadence_create(
    active: bool,
    automatic: bool,
    group_path: str,
    client_mutation_id: Optional[str] = None,
    description: Optional[str] = None,
    duration_in_weeks: Optional[int] = None,
    iterations_in_advance: Optional[int] = None,
    roll_over: Optional[bool] = None,
    start_date: Optional[str] = None,
    title: Optional[str] = None,
) -> Dict[str, Any]:
    """Creates a new iteration cadence.

    Args:
        active (bool): Whether the iteration cadence is active.
        automatic (bool): Whether the iteration cadence should automatically generate upcoming iterations.
        group_path (str): Group where the iteration cadence is created.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        description (Optional[str]): Description of the iteration cadence. Maximum length is 5000 characters.
        duration_in_weeks (Optional[int]): Duration in weeks of the iterations within this cadence.
        iterations_in_advance (Optional[int]): Upcoming iterations to be created when iteration cadence is set to automatic.
        roll_over (Optional[bool]): Whether the iteration cadence should roll over issues to the next iteration or not.
        start_date (Optional[str]): Timestamp of the automation start date (e.g., ISO 8601 string).
        title (Optional[str]): Title of the iteration cadence.
    """
    query = """
    mutation IterationCadenceCreate(
      $active: Boolean!,
      $automatic: Boolean!,
      $groupPath: ID!,
      $clientMutationId: String,
      $description: String,
      $durationInWeeks: Int,
      $iterationsInAdvance: Int,
      $rollOver: Boolean,
      $startDate: Time,
      $title: String
    ) {
      iterationCadenceCreate(input: {
        active: $active,
        automatic: $automatic,
        groupPath: $groupPath,
        clientMutationId: $clientMutationId,
        description: $description,
        durationInWeeks: $durationInWeeks,
        iterationsInAdvance: $iterationsInAdvance,
        rollOver: $rollOver,
        startDate: $startDate,
        title: $title
      }) {
        clientMutationId
        errors
        iterationCadence {
          id
          title
          description
          active
          automatic
          durationInWeeks
          iterationsInAdvance
          rollOver
          startDate
          group {
            id
            fullPath
          }
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "active": active,
        "automatic": automatic,
        "groupPath": group_path,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id
    if description is not None:
        variables["description"] = description
    if duration_in_weeks is not None:
        variables["durationInWeeks"] = duration_in_weeks
    if iterations_in_advance is not None:
        variables["iterationsInAdvance"] = iterations_in_advance
    if roll_over is not None:
        variables["rollOver"] = roll_over
    if start_date is not None:
        variables["startDate"] = start_date
    if title is not None:
        variables["title"] = title

    return _graphql_request(query, variables)

# --- Mutation.iterationCadenceDestroy ---
@mcp.tool()
def iteration_cadence_destroy(id: str, client_mutation_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Destroys an iteration cadence.

    Args:
        id (str): Global ID of the iteration cadence.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation IterationCadenceDestroy($clientMutationId: String, $id: IterationsCadenceID!) {
      iterationCadenceDestroy(input: { clientMutationId: $clientMutationId, id: $id }) {
        clientMutationId
        errors
        group {
          id
          name
          fullPath
          description
        }
      }
    }
    """
    variables = {
        "clientMutationId": client_mutation_id,
        "id": id,
    }
    return _graphql_request(query, variables=variables)

# --- Mutation.iterationCadenceUpdate ---
from typing import Optional, Dict, Any

@mcp.tool()
def iteration_cadence_update(
    id: str,
    active: Optional[bool] = None,
    automatic: Optional[bool] = None,
    client_mutation_id: Optional[str] = None,
    description: Optional[str] = None,
    duration_in_weeks: Optional[int] = None,
    iterations_in_advance: Optional[int] = None,
    roll_over: Optional[bool] = None,
    start_date: Optional[str] = None,
    title: Optional[str] = None,
) -> Dict[str, Any]:
    """Updates an existing iteration cadence.

    Args:
        id: Global ID of the iteration cadence.
        active: Whether the iteration cadence is active.
        automatic: Whether the iteration cadence should automatically generate upcoming iterations.
        client_mutation_id: A unique identifier for the client performing the mutation.
        description: Description of the iteration cadence. Maximum length is 5000 characters.
        duration_in_weeks: Duration in weeks of the iterations within this cadence.
        iterations_in_advance: Upcoming iterations to be created when iteration cadence is set to automatic.
        roll_over: Whether the iteration cadence should roll over issues to the next iteration or not.
        start_date: Timestamp of the automation start date (e.g., "YYYY-MM-DDTHH:MM:SSZ").
        title: Title of the iteration cadence.
    """
    graphql_variables = {}
    mutation_args_input = []
    mutation_signature_parts = []

    # Required argument
    graphql_variables["id"] = id
    mutation_signature_parts.append("$id: IterationsCadenceID!")
    mutation_args_input.append("id: $id")

    # Optional arguments
    if active is not None:
        graphql_variables["active"] = active
        mutation_signature_parts.append("$active: Boolean")
        mutation_args_input.append("active: $active")
    if automatic is not None:
        graphql_variables["automatic"] = automatic
        mutation_signature_parts.append("$automatic: Boolean")
        mutation_args_input.append("automatic: $automatic")
    if client_mutation_id is not None:
        graphql_variables["clientMutationId"] = client_mutation_id
        mutation_signature_parts.append("$clientMutationId: String")
        mutation_args_input.append("clientMutationId: $clientMutationId")
    if description is not None:
        graphql_variables["description"] = description
        mutation_signature_parts.append("$description: String")
        mutation_args_input.append("description: $description")
    if duration_in_weeks is not None:
        graphql_variables["durationInWeeks"] = duration_in_weeks
        mutation_signature_parts.append("$durationInWeeks: Int")
        mutation_args_input.append("durationInWeeks: $durationInWeeks")
    if iterations_in_advance is not None:
        graphql_variables["iterationsInAdvance"] = iterations_in_advance
        mutation_signature_parts.append("$iterationsInAdvance: Int")
        mutation_args_input.append("iterationsInAdvance: $iterationsInAdvance")
    if roll_over is not None:
        graphql_variables["rollOver"] = roll_over
        mutation_signature_parts.append("$rollOver: Boolean")
        mutation_args_input.append("rollOver: $rollOver")
    if start_date is not None:
        graphql_variables["startDate"] = start_date
        mutation_signature_parts.append("$startDate: Time")
        mutation_args_input.append("startDate: $startDate")
    if title is not None:
        graphql_variables["title"] = title
        mutation_signature_parts.append("$title: String")
        mutation_args_input.append("title: $title")

    mutation_signature = ", ".join(mutation_signature_parts)
    if mutation_signature:
        mutation_signature = f"({mutation_signature})"

    input_args_str = ", ".join(mutation_args_input)

    query = f"""
    mutation IterationCadenceUpdate{mutation_signature} {{
      iterationCadenceUpdate(input: {{ {input_args_str} }}) {{
        clientMutationId
        errors
        iterationCadence {{
          id
          title
          description
          active
          automatic
          durationInWeeks
          startDate
          iterationsInAdvance
          rollOver
        }}
      }}
    }}
    """
    return _graphql_request(query, graphql_variables)

# --- Mutation.iterationCreate ---
@mcp.tool()
def iteration_create(
    client_mutation_id: Optional[str] = None,
    description: Optional[str] = None,
    due_date: Optional[str] = None,
    group_path: Optional[str] = None,
    iterations_cadence_id: Optional[str] = None,
    project_path: Optional[str] = None,
    start_date: Optional[str] = None,
    title: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Creates a new iteration.

    Args:
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        description (Optional[str]): Description of the iteration.
        due_date (Optional[str]): End date of the iteration.
        group_path (Optional[str]): Full path of the group with which the resource is associated.
        iterations_cadence_id (Optional[str]): Global ID of the iteration cadence to be assigned to the new iteration.
        project_path (Optional[str]): Full path of the project with which the resource is associated.
        start_date (Optional[str]): Start date of the iteration.
        title (Optional[str]): Title of the iteration.
    """
    query = """
    mutation IterationCreate($input: IterationCreateInput!) {
      iterationCreate(input: $input) {
        clientMutationId
        errors
        iteration {
          id
          title
          description
          startDate
          dueDate
          state
          webUrl
        }
      }
    }
    """
    input_args = {}
    if client_mutation_id is not None:
        input_args["clientMutationId"] = client_mutation_id
    if description is not None:
        input_args["description"] = description
    if due_date is not None:
        input_args["dueDate"] = due_date
    if group_path is not None:
        input_args["groupPath"] = group_path
    if iterations_cadence_id is not None:
        input_args["iterationsCadenceId"] = iterations_cadence_id
    if project_path is not None:
        input_args["projectPath"] = project_path
    if start_date is not None:
        input_args["startDate"] = start_date
    if title is not None:
        input_args["title"] = title

    variables = {"input": input_args}
    return _graphql_request(query, variables)

# --- Mutation.iterationDelete ---
@mcp.tool()
def iteration_delete(
    id: str,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Deletes an iteration.

    Args:
        id: ID of the iteration.
        client_mutation_id: A unique identifier for the client performing the mutation.
    """
    query = """
    mutation IterationDelete($id: IterationID!, $clientMutationId: String) {
      iterationDelete(input: { id: $id, clientMutationId: $clientMutationId }) {
        clientMutationId
        errors
        group {
          id
          name
          fullPath
          webUrl
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "id": id,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables=variables)

# --- Mutation.jiraImportStart ---
@mcp.tool()
def jira_import_start(
    jira_project_key: str,
    project_path: str,
    client_mutation_id: Optional[str] = None,
    jira_project_name: Optional[str] = None,
    users_mapping: Optional[List[List[Dict[str, Any]]]] = None,
) -> Dict[str, Any]:
    """Start a Jira project import into a GitLab project.

    Args:
        jira_project_key (str): Project key of the importer Jira project.
        project_path (str): Project to import the Jira project into.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        jira_project_name (Optional[str]): Project name of the importer Jira project.
        users_mapping (Optional[List[List[Dict[str, Any]]]]): Mapping of Jira to GitLab users.
            Each inner list should contain objects representing JiraUsersMappingInputType.
    """
    variables: Dict[str, Any] = {
        "jiraProjectKey": jira_project_key,
        "projectPath": project_path,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id
    if jira_project_name is not None:
        variables["jiraProjectName"] = jira_project_name
    if users_mapping is not None:
        variables["usersMapping"] = users_mapping

    query = """
    mutation JiraImportStart(
      $clientMutationId: String
      $jiraProjectKey: String!
      $jiraProjectName: String
      $projectPath: ID!
      $usersMapping: [[JiraUsersMappingInputType!]]
    ) {
      jiraImportStart(input: {
        clientMutationId: $clientMutationId
        jiraProjectKey: $jiraProjectKey
        jiraProjectName: $jiraProjectName
        projectPath: $projectPath
        usersMapping: $usersMapping
      }) {
        clientMutationId
        errors
        jiraImport {
          id
          status
          scheduledAt
          jiraProjectKey
          jiraProjectName
          projectId
        }
      }
    }
    """
    return _graphql_request(query, variables)

# --- Mutation.jiraImportUsers ---
@mcp.tool()
def jira_import_users(
    project_path: str,
    client_mutation_id: Optional[str] = None,
    start_at: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Imports Jira users into a GitLab project.

    Args:
        project_path (str): Project to import the Jira users into.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        start_at (Optional[int]): Index of the record the import should started at, default 0 (50 records returned).
    """
    query = """
    mutation JiraImportUsers(
      $clientMutationId: String
      $projectPath: ID!
      $startAt: Int
    ) {
      jiraImportUsers(input: {
        clientMutationId: $clientMutationId
        projectPath: $projectPath
        startAt: $startAt
      }) {
        clientMutationId
        errors
        jiraUsers {
          id
          name
          email
          jiraAccountId
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "projectPath": project_path,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id
    if start_at is not None:
        variables["startAt"] = start_at

    return _graphql_request(query, variables)

# --- Mutation.jobArtifactsDestroy ---
@mcp.tool()
def job_artifacts_destroy(id: str, client_mutation_id: Optional[str] = None) -> Dict[str, Any]:
    """Destroys job artifacts for a given job ID.

    Args:
        id: ID of the job to mutate.
        client_mutation_id: A unique identifier for the client performing the mutation.
    """
    query = """
    mutation JobArtifactsDestroy($id: CiBuildID!, $clientMutationId: String) {
      jobArtifactsDestroy(input: { id: $id, clientMutationId: $clientMutationId }) {
        clientMutationId
        destroyedArtifactsCount
        errors
        job {
          id
          name
        }
      }
    }
    """
    variables = {
        "id": id,
        "clientMutationId": client_mutation_id,
    }
    return _graphql_request(query, variables)

# --- Mutation.jobCancel ---
@mcp.tool()
def job_cancel(id: str, client_mutation_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Cancels a GitLab CI/CD job.

    Args:
        id: ID of the job to mutate.
        client_mutation_id: A unique identifier for the client performing the mutation.
    """
    query = """
    mutation JobCancel($id: CiBuildID!, $clientMutationId: String) {
      jobCancel(input: { id: $id, clientMutationId: $clientMutationId }) {
        clientMutationId
        errors
        job {
          id
          name
          status
          stage {
            id
            name
          }
        }
      }
    }
    """
    variables = {
        "id": id,
        "clientMutationId": client_mutation_id,
    }
    return _graphql_request(query, variables)

# --- Mutation.jobPlay ---
@mcp.tool()
def job_play(id: str, client_mutation_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Play a GitLab CI job.

    Args:
        id: ID of the job to play.
        client_mutation_id: A unique identifier for the client performing the mutation.
    """
    query = """
    mutation jobPlayMutation($id: CiBuildID!, $clientMutationId: String) {
      jobPlay(input: { id: $id, clientMutationId: $clientMutationId }) {
        clientMutationId
        errors
        job {
          id
          name
          status
          detailedStatus {
            id
            group
            icon
            text
          }
          stage {
            id
            name
          }
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "id": id,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.jobRetry ---
@mcp.tool()
def job_retry(
    job_id: str,
    client_mutation_id: Optional[str] = None,
    variables: Optional[List[List[Dict[str, str]]]] = None,
) -> Dict[str, Any]:
    """
    Retries a job in GitLab.

    Args:
        job_id: ID of the job to mutate.
        client_mutation_id: A unique identifier for the client performing the mutation.
        variables: Variables to use when retrying a manual job. Each inner list should contain dictionaries with 'key' and 'value'.
    """
    _input: Dict[str, Any] = {
        "id": job_id,
    }
    if client_mutation_id is not None:
        _input["clientMutationId"] = client_mutation_id
    if variables is not None:
        _input["variables"] = variables

    query = """
    mutation JobRetry($input: JobRetryInput!) {
      jobRetry(input: $input) {
        clientMutationId
        errors
        job {
          id
          name
          status
          stage {
            id
            name
          }
          ref
          pipeline {
            id
            iid
            sha
          }
          createdAt
          finishedAt
          duration
          user {
            id
            username
          }
        }
      }
    }
    """
    return _graphql_request(query, variables={"input": _input})

# --- Mutation.jobUnschedule ---
@mcp.tool()
def job_unschedule(id: str, client_mutation_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Unschedules a job in GitLab.

    Args:
        id (str): ID of the job to mutate.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    input_args = [f'id: "{id}"']
    if client_mutation_id is not None:
        input_args.append(f'clientMutationId: "{client_mutation_id}"')

    input_string = ", ".join(input_args)

    query = f"""
    mutation {{
        jobUnschedule(input: {{ {input_string} }}) {{
            clientMutationId
            errors
            job {{
                id
                name
                status
                stage
                allowFailure
                createdAt
                duration
                finishedAt
                queuedAt
                startedAt
                pipeline {{
                    id
                    iid
                    status
                    sha
                }}
            }}
        }}
    }}
    """
    return _graphql_request(query)

# --- Mutation.labelCreate ---
@mcp.tool()
def label_create(
    title: str,
    color: Optional[str] = None,
    description: Optional[str] = None,
    group_path: Optional[str] = None,
    project_path: Optional[str] = None,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Creates a new label.

    Args:
        title: Title of the label.
        color: The color of the label given in 6-digit hex notation with leading '#' sign (for example, `#FFAABB`) or one of the CSS color names.
        description: Description of the label.
        group_path: Full path of the group with which the resource is associated.
        project_path: Full path of the project with which the resource is associated.
        client_mutation_id: A unique identifier for the client performing the mutation.
    """
    query = """
        mutation LabelCreate(
            $title: String!
            $color: String
            $description: String
            $groupPath: ID
            $projectPath: ID
            $clientMutationId: String
        ) {
            labelCreate(input: {
                title: $title
                color: $color
                description: $description
                groupPath: $groupPath
                projectPath: $projectPath
                clientMutationId: $clientMutationId
            }) {
                clientMutationId
                errors
                label {
                    id
                    title
                    color
                    description
                    createdAt
                    updatedAt
                }
            }
        }
    """
    variables: Dict[str, Any] = {
        "title": title,
    }
    if color is not None:
        variables["color"] = color
    if description is not None:
        variables["description"] = description
    if group_path is not None:
        variables["groupPath"] = group_path
    if project_path is not None:
        variables["projectPath"] = project_path
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.markAsSpamSnippet ---
@mcp.tool()
def mark_as_spam_snippet(id: str, client_mutation_id: Optional[str] = None) -> Dict[str, Any]:
    """Mark a snippet as spam.

    Args:
        id (str): Global ID of the snippet to update.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation MarkAsSpamSnippet($input: MarkAsSpamSnippetInput!) {
      markAsSpamSnippet(input: $input) {
        clientMutationId
        errors
        snippet {
          id
          title
          description
          fileName
          updatedAt
        }
      }
    }
    """
    variables: Dict[str, Any] = {"input": {"id": id}}
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.mergeRequestAccept ---
@mcp.tool()
def merge_request_accept(
    iid: str,
    project_path: str,
    sha: str,
    client_mutation_id: Optional[str] = None,
    commit_message: Optional[str] = None,
    should_remove_source_branch: Optional[bool] = None,
    squash: Optional[bool] = None,
    squash_commit_message: Optional[str] = None,
    strategy: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Accepts a merge request, merging the source branch into the target branch.

    Args:
        iid (str): IID of the merge request to mutate.
        project_path (str): Project the merge request to mutate is in.
        sha (str): HEAD SHA at the time when this merge was requested.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        commit_message (Optional[str]): Custom merge commit message.
        should_remove_source_branch (Optional[bool]): Should the source branch be removed.
        squash (Optional[bool]): Squash commits on the source branch before merge.
        squash_commit_message (Optional[str]): Custom squash commit message (if squash is true).
        strategy (Optional[str]): How to merge this merge request (e.g., 'MERGE_TRAIN_STRATEGY').
    """
    query = """
    mutation MergeRequestAccept($input: MergeRequestAcceptInput!) {
      mergeRequestAccept(input: $input) {
        clientMutationId
        errors
        mergeRequest {
          id
          iid
          title
          state
          webUrl
          sourceBranch
          targetBranch
          squashOnMerge
          shouldRemoveSourceBranch
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "iid": iid,
            "projectPath": project_path,
            "sha": sha,
        }
    }
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id
    if commit_message is not None:
        variables["input"]["commitMessage"] = commit_message
    if should_remove_source_branch is not None:
        variables["input"]["shouldRemoveSourceBranch"] = should_remove_source_branch
    if squash is not None:
        variables["input"]["squash"] = squash
    if squash_commit_message is not None:
        variables["input"]["squashCommitMessage"] = squash_commit_message
    if strategy is not None:
        variables["input"]["strategy"] = strategy

    return _graphql_request(query, variables)

# --- Mutation.mergeRequestCreate ---
@mcp.tool()
def merge_request_create(
    project_path: str,
    source_branch: str,
    target_branch: str,
    title: str,
    client_mutation_id: Optional[str] = None,
    description: Optional[str] = None,
    labels: Optional[List[List[str]]] = None,
) -> Dict[str, Any]:
    """
    Creates a new merge request in a project.

    Args:
        project_path (str): Project full path the merge request is associated with.
        source_branch (str): Source branch of the merge request.
        target_branch (str): Target branch of the merge request.
        title (str): Title of the merge request.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        description (Optional[str]): Description of the merge request (Markdown rendered as HTML for caching).
        labels (Optional[List[List[str]]]): Labels of the merge request.
    """
    query = """
    mutation mergeRequestCreate(
      $projectPath: ID!,
      $sourceBranch: String!,
      $targetBranch: String!,
      $title: String!,
      $clientMutationId: String,
      $description: String,
      $labels: [[String!]]
    ) {
      mergeRequestCreate(input: {
        projectPath: $projectPath,
        sourceBranch: $sourceBranch,
        targetBranch: $targetBranch,
        title: $title,
        clientMutationId: $clientMutationId,
        description: $description,
        labels: $labels
      }) {
        clientMutationId
        errors
        mergeRequest {
          id
          iid
          title
          webUrl
          state
          author {
            username
          }
          targetBranch
          sourceBranch
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "projectPath": project_path,
        "sourceBranch": source_branch,
        "targetBranch": target_branch,
        "title": title,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id
    if description is not None:
        variables["description"] = description
    if labels is not None:
        variables["labels"] = labels

    return _graphql_request(query, variables)

# --- Mutation.mergeRequestReviewerRereview ---
@mcp.tool()
def merge_request_reviewer_rereview(
    iid: str,
    project_path: str,
    user_id: str,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Request a new review from a specific user for a merge request.

    Args:
        iid: IID of the merge request to mutate.
        project_path: Project the merge request to mutate is in.
        user_id: User ID for the user that has been requested for a new review.
        client_mutation_id: A unique identifier for the client performing the mutation.
    """
    query = """
    mutation mergeRequestReviewerRereviewMutation(
      $iid: String!,
      $projectPath: ID!,
      $userId: UserID!,
      $clientMutationId: String
    ) {
      mergeRequestReviewerRereview(input: {
        iid: $iid,
        projectPath: $projectPath,
        userId: $userId,
        clientMutationId: $clientMutationId
      }) {
        clientMutationId
        errors
        mergeRequest {
          id
          iid
          title
          webUrl
          state
          reviewers {
            nodes {
              id
              username
              webUrl
            }
          }
        }
      }
    }
    """
    variables = {
        "iid": iid,
        "projectPath": project_path,
        "userId": user_id,
        "clientMutationId": client_mutation_id,
    }
    return _graphql_request(query, variables)

# --- Mutation.mergeRequestSetAssignees ---
@mcp.tool()
def merge_request_set_assignees(
    assignee_usernames: List[str],
    iid: str,
    project_path: str,
    client_mutation_id: Optional[str] = None,
    operation_mode: Optional[str] = None,
) -> Dict[str, Any]:
    """Assigns users to a merge request.

    Args:
        assignee_usernames: Usernames to assign to the resource. Replaces existing assignees by default.
        iid: IID of the merge request to mutate.
        project_path: Project the merge request to mutate is in.
        client_mutation_id: A unique identifier for the client performing the mutation.
        operation_mode: Operation to perform. Defaults to REPLACE.
    """
    query = """
    mutation MergeRequestSetAssignees($input: MergeRequestSetAssigneesInput!) {
      mergeRequestSetAssignees(input: $input) {
        clientMutationId
        errors
        mergeRequest {
          id
          iid
          title
          webUrl
          assignees {
            nodes {
              id
              username
              name
            }
          }
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "assigneeUsernames": assignee_usernames,
            "iid": iid,
            "projectPath": project_path,
        }
    }
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id
    if operation_mode is not None:
        variables["input"]["operationMode"] = operation_mode

    return _graphql_request(query, variables)

# --- Mutation.mergeRequestSetDraft ---
@mcp.tool()
def merge_request_set_draft(
    draft: bool,
    iid: str,
    project_path: str,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Sets the draft status of a merge request.

    Args:
        draft (bool): Whether or not to set the merge request as a draft.
        iid (str): IID of the merge request to mutate.
        project_path (str): Project the merge request to mutate is in (e.g., 'group/subgroup/project').
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
mutation MergeRequestSetDraft($draft: Boolean!, $iid: String!, $projectPath: ID!, $clientMutationId: String) {
  mergeRequestSetDraft(input: {
    draft: $draft,
    iid: $iid,
    projectPath: $projectPath,
    clientMutationId: $clientMutationId
  }) {
    clientMutationId
    errors
    mergeRequest {
      id
      iid
      title
      webUrl
      draft
      state
      author {
        username
      }
    }
  }
}
"""
    variables = {
        "draft": draft,
        "iid": iid,
        "projectPath": project_path,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.mergeRequestSetLabels ---
@mcp.tool()
def merge_request_set_labels(
    iid: str,
    project_path: str,
    label_ids: Optional[List[str]] = None,
    operation_mode: Optional[str] = None,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Sets labels for a merge request, replacing existing ones by default.

    Args:
        iid (str): IID of the merge request to mutate.
        project_path (str): Project the merge request to mutate is in (e.g., 'group/project').
        label_ids (Optional[List[str]]): List of global Label IDs to set.
        operation_mode (Optional[str]): Changes how labels are applied (e.g., "REPLACE", "ADD", "REMOVE").
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation MergeRequestSetLabels($input: MergeRequestSetLabelsInput!) {
      mergeRequestSetLabels(input: $input) {
        clientMutationId
        errors
        mergeRequest {
          id
          iid
          title
          webUrl
          state
          labels(first: 5) {
            nodes {
              id
              title
              color
            }
          }
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "iid": iid,
            "projectPath": project_path,
        }
    }
    if label_ids is not None:
        variables["input"]["labelIds"] = label_ids
    if operation_mode is not None:
        variables["input"]["operationMode"] = operation_mode
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.mergeRequestSetLocked ---
@mcp.tool()
def merge_request_set_locked(
    iid: str,
    locked: bool,
    project_path: str,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Set the locked status of a merge request.

    Args:
        iid: IID of the merge request to mutate.
        locked: Whether or not to lock the merge request.
        project_path: Project the merge request to mutate is in.
        client_mutation_id: A unique identifier for the client performing the mutation.
    """
    query = """
    mutation MergeRequestSetLocked($iid: String!, $locked: Boolean!, $projectPath: ID!, $clientMutationId: String) {
      mergeRequestSetLocked(input: { iid: $iid, locked: $locked, projectPath: $projectPath, clientMutationId: $clientMutationId }) {
        errors
        clientMutationId
        mergeRequest {
          id
          iid
          title
          state
          locked
          webUrl
          # Add more fields from MergeRequest if needed
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "iid": iid,
        "locked": locked,
        "projectPath": project_path,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables=variables)

# --- Mutation.mergeRequestSetMilestone ---
@mcp.tool()
def merge_request_set_milestone(
    iid: str,
    project_path: str,
    milestone_id: Optional[str] = None,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Set the milestone for a GitLab merge request.

    Args:
        iid: IID of the merge request to mutate.
        project_path: Project the merge request to mutate is in (e.g., "group/project").
        milestone_id: Milestone to assign to the merge request.
        client_mutation_id: A unique identifier for the client performing the mutation.
    """
    query = """
    mutation MergeRequestSetMilestone($iid: String!, $projectPath: ID!, $milestoneId: MilestoneID, $clientMutationId: String) {
      mergeRequestSetMilestone(input: {
        iid: $iid,
        projectPath: $projectPath,
        milestoneId: $milestoneId,
        clientMutationId: $clientMutationId
      }) {
        clientMutationId
        errors
        mergeRequest {
          id
          iid
          title
          webUrl
          milestone {
            id
            title
            description
            state
          }
        }
      }
    }
    """
    variables = {
        "iid": iid,
        "projectPath": project_path,
        "milestoneId": milestone_id,
        "clientMutationId": client_mutation_id,
    }
    return _graphql_request(query, variables)

# --- Mutation.mergeRequestSetReviewers ---
@mcp.tool()
def merge_request_set_reviewers(
    iid: str,
    project_path: str,
    reviewer_usernames: List[List[str]],
    client_mutation_id: Optional[str] = None,
    operation_mode: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Sets or replaces reviewers for a GitLab merge request.

    Args:
        iid (str): IID of the merge request to mutate.
        project_path (str): Project the merge request to mutate is in (e.g., "group/project").
        reviewer_usernames (List[List[str]]): Usernames of reviewers to assign.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        operation_mode (Optional[str]): Operation to perform, e.g., "REPLACE" or "APPEND". Defaults to REPLACE.
    """
    query = """
    mutation mergeRequestSetReviewers($input: MergeRequestSetReviewersInput!) {
      mergeRequestSetReviewers(input: $input) {
        clientMutationId
        errors
        mergeRequest {
          id
          iid
          title
          webUrl
          reviewers {
            nodes {
              id
              username
              webUrl
            }
          }
        }
      }
    }
    """
    variables = {
        "input": {
            "iid": iid,
            "projectPath": project_path,
            "reviewerUsernames": reviewer_usernames,
        }
    }
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id
    if operation_mode is not None:
        variables["input"]["operationMode"] = operation_mode

    return _graphql_request(query, variables)

# --- Mutation.mergeRequestSetSubscription ---
@mcp.tool()
def merge_request_set_subscription(
    iid: str,
    project_path: str,
    subscribed_state: bool,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Sets the subscription state for a merge request.

    Args:
        iid (str): IID of the merge request to mutate.
        project_path (str): Project the merge request to mutate is in.
        subscribed_state (bool): Desired state of the subscription.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation MergeRequestSetSubscription($input: MergeRequestSetSubscriptionInput!) {
      mergeRequestSetSubscription(input: $input) {
        clientMutationId
        errors
        mergeRequest {
          id
          iid
          title
          webUrl
          subscribed
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "iid": iid,
            "projectPath": project_path,
            "subscribedState": subscribed_state,
        }
    }
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables=variables)

# --- Mutation.mergeRequestUpdate ---
@mcp.tool()
def merge_request_update(
    iid: str,
    project_path: str,
    client_mutation_id: Optional[str] = None,
    description: Optional[str] = None,
    state: Optional[str] = None,
    target_branch: Optional[str] = None,
    title: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Update attributes of a GitLab merge request.

    Args:
        iid (str): IID of the merge request to mutate.
        project_path (str): Project the merge request to mutate is in (e.g., 'group/project').
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        description (Optional[str]): Description of the merge request.
        state (Optional[str]): Action to perform to change the state (e.g., 'merged', 'closed', 'reopen').
        target_branch (Optional[str]): Target branch of the merge request.
        title (Optional[str]): Title of the merge request.
    """
    query = """
    mutation MergeRequestUpdate($input: MergeRequestUpdateInput!) {
      mergeRequestUpdate(input: $input) {
        clientMutationId
        errors
        mergeRequest {
          id
          iid
          title
          descriptionHtml
          state
          webUrl
          sourceBranch
          targetBranch
          author {
            username
          }
        }
      }
    }
    """
    variables = {
        "input": {
            "iid": iid,
            "projectPath": project_path,
        }
    }
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id
    if description is not None:
        variables["input"]["description"] = description
    if state is not None:
        variables["input"]["state"] = state
    if target_branch is not None:
        variables["input"]["targetBranch"] = target_branch
    if title is not None:
        variables["input"]["title"] = title

    return _graphql_request(query, variables)

# --- Mutation.namespaceBanDestroy ---
@mcp.tool()
def namespace_ban_destroy(id: str, client_mutation_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Removes an existing namespace ban.

    Args:
        id: Global ID of the namespace ban to remove.
        client_mutation_id: A unique identifier for the client performing the mutation.
    """
    query = """
        mutation NamespaceBanDestroy($id: NamespacesNamespaceBanID!, $clientMutationId: String) {
            namespaceBanDestroy(input: {
                id: $id,
                clientMutationId: $clientMutationId
            }) {
                clientMutationId
                errors
                namespaceBan {
                    id
                    createdAt
                    updatedAt
                    user {
                        id
                        username
                        name
                        state
                    }
                    namespace {
                        id
                        fullPath
                        name
                    }
                }
            }
        }
    """
    variables: Dict[str, Any] = {
        "id": id,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.namespaceCiCdSettingsUpdate ---
@mcp.tool()
def namespace_ci_cd_settings_update(
    full_path: str,
    allow_stale_runner_pruning: Optional[bool] = None,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Updates the CI/CD settings for a given namespace.

    Args:
        full_path (str): Full path of the namespace the settings belong to.
        allow_stale_runner_pruning (Optional[bool]): Indicates if stale runners directly belonging to this namespace should be periodically pruned.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation NamespaceCiCdSettingsUpdate(
      $fullPath: ID!
      $allowStaleRunnerPruning: Boolean
      $clientMutationId: String
    ) {
      namespaceCiCdSettingsUpdate(input: {
        fullPath: $fullPath
        allowStaleRunnerPruning: $allowStaleRunnerPruning
        clientMutationId: $clientMutationId
      }) {
        ciCdSettings {
          id
          allowStaleRunnerPruning
          runnerToken
        }
        clientMutationId
        errors
      }
    }
    """
    variables = {
        "fullPath": full_path,
        "allowStaleRunnerPruning": allow_stale_runner_pruning,
        "clientMutationId": client_mutation_id,
    }
    return _graphql_request(query, variables)

# --- Mutation.namespaceIncreaseStorageTemporarily ---
@mcp.tool()
def namespace_increase_storage_temporarily(
    namespace_id: str,
    client_mutation_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Increases the storage limit temporarily for a given namespace.

    Args:
        namespace_id: Global ID of the namespace to mutate.
        client_mutation_id: A unique identifier for the client performing the mutation.
    """
    query_variables = {
        "namespaceId": namespace_id,
    }
    query_args = "$namespaceId: NamespaceID!"

    if client_mutation_id is not None:
        query_variables["clientMutationId"] = client_mutation_id
        query_args += ", $clientMutationId: String"

    query = f"""
    mutation NamespaceIncreaseStorageTemporarily({query_args}) {{
      namespaceIncreaseStorageTemporarily(input: {{
        id: $namespaceId,
        {"clientMutationId: $clientMutationId," if client_mutation_id is not None else ""}
      }}) {{
        clientMutationId
        errors
        namespace {{
          id
          name
          fullPath
          storageSize
          actualRepositorySizeLimit
          temporaryStorageIncreaseEnabled
          temporaryStorageIncreaseEndDate
        }}
      }}
    }}
    """
    return _graphql_request(query, query_variables)

# --- Mutation.oncallRotationCreate ---
@mcp.tool()
def oncall_rotation_create(
    name: str,
    participants: List[List[Dict[str, Any]]],
    project_path: str,
    rotation_length: Dict[str, Any],
    schedule_iid: str,
    starts_at: Dict[str, Any],
    active_period: Optional[Dict[str, Any]] = None,
    client_mutation_id: Optional[str] = None,
    ends_at: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Creates a new on-call rotation within a specified schedule.

    Args:
        name (str): Name of the on-call rotation.
        participants (List[List[Dict[str, Any]]]): Usernames of users participating in the on-call rotation.
        project_path (str): Project path where the on-call schedule resides.
        rotation_length (Dict[str, Any]): Rotation length configuration.
        schedule_iid (str): IID of the on-call schedule.
        starts_at (Dict[str, Any]): Start date and time of the on-call rotation.
        active_period (Optional[Dict[str, Any]]): Active period of time for the rotation.
        client_mutation_id (Optional[str]): A unique identifier for the client.
        ends_at (Optional[Dict[str, Any]]): End date and time of the on-call rotation.
    """
    query = """
    mutation OncallRotationCreate($input: OncallRotationCreateInput!) {
      oncallRotationCreate(input: $input) {
        clientMutationId
        errors
        oncallRotation {
          id
          name
          activePeriod {
            startTime
            endTime
          }
          startsAt {
            date
            time
            zone
          }
          endsAt {
            date
            time
            zone
          }
          participants {
            user {
              username
              name
            }
          }
          rotationLength {
            length
            unit
          }
          schedule {
            id
            iid
          }
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "name": name,
            "participants": participants,
            "projectPath": project_path,
            "rotationLength": rotation_length,
            "scheduleIid": schedule_iid,
            "startsAt": starts_at,
        }
    }
    if active_period is not None:
        variables["input"]["activePeriod"] = active_period
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id
    if ends_at is not None:
        variables["input"]["endsAt"] = ends_at

    return _graphql_request(query, variables)

# --- Mutation.oncallRotationDestroy ---
@mcp.tool()
def oncall_rotation_destroy(
    id: str,
    project_path: str,
    schedule_iid: str,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Destroys an on-call rotation.

    Args:
        id (str): ID of the on-call rotation to remove.
        project_path (str): Project to remove the on-call schedule from.
        schedule_iid (str): IID of the on-call schedule to the on-call rotation belongs to.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation OncallRotationDestroy($input: OncallRotationDestroyInput!) {
      oncallRotationDestroy(input: $input) {
        clientMutationId
        errors
        oncallRotation {
          id
          name
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "id": id,
            "projectPath": project_path,
            "scheduleIid": schedule_iid,
        }
    }
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables=variables)

# --- Mutation.oncallRotationUpdate ---
@mcp.tool()
def oncall_rotation_update(
    id: str,
    active_period: Optional[Dict[str, Any]] = None,
    client_mutation_id: Optional[str] = None,
    ends_at: Optional[Dict[str, Any]] = None,
    name: Optional[str] = None,
    participants: Optional[List[List[Dict[str, Any]]]] = None,
    rotation_length: Optional[Dict[str, Any]] = None,
    starts_at: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Updates an existing on-call rotation within an on-call schedule.

    Args:
        id: ID of the on-call rotation to update.
        active_period: Active period of time that the on-call rotation should take place.
        client_mutation_id: A unique identifier for the client performing the mutation.
        ends_at: End date and time of the on-call rotation, in the timezone of the on-call schedule.
        name: Name of the on-call rotation.
        participants: Usernames of users participating in the on-call rotation.
        rotation_length: Rotation length of the on-call rotation.
        starts_at: Start date and time of the on-call rotation, in the timezone of the on-call schedule.
    """
    mutation_args = {
        "id": "$id"
    }
    variables = {
        "id": id
    }

    if active_period is not None:
        mutation_args["activePeriod"] = "$activePeriod"
        variables["activePeriod"] = active_period
    if client_mutation_id is not None:
        mutation_args["clientMutationId"] = "$clientMutationId"
        variables["clientMutationId"] = client_mutation_id
    if ends_at is not None:
        mutation_args["endsAt"] = "$endsAt"
        variables["endsAt"] = ends_at
    if name is not None:
        mutation_args["name"] = "$name"
        variables["name"] = name
    if participants is not None:
        mutation_args["participants"] = "$participants"
        variables["participants"] = participants
    if rotation_length is not None:
        mutation_args["rotationLength"] = "$rotationLength"
        variables["rotationLength"] = rotation_length
    if starts_at is not None:
        mutation_args["startsAt"] = "$startsAt"
        variables["startsAt"] = starts_at

    # Construct the GraphQL variable definitions
    variable_definitions = ", ".join([
        f"${name}: {GraphQL_type}"
        for name, GraphQL_type in {
            "id": "IncidentManagementOncallRotationID!",
            "activePeriod": "OncallRotationActivePeriodInputType",
            "clientMutationId": "String",
            "endsAt": "OncallRotationDateInputType",
            "name": "String",
            "participants": "[[OncallUserInputType!]]",
            "rotationLength": "OncallRotationLengthInputType",
            "startsAt": "OncallRotationDateInputType",
        }.items() if name in variables
    ])
    
    mutation_input_string = ", ".join([f"{k}: {v}" for k, v in mutation_args.items()])

    query = f"""
    mutation ({variable_definitions}) {{
        oncallRotationUpdate(input: {{ {mutation_input_string} }}) {{
            clientMutationId
            errors
            oncallRotation {{
                id
                name
                startsAt {{
                    date
                    time
                }}
                endsAt {{
                    date
                    time
                }}
                activePeriod {{
                    startTime
                    endTime
                }}
                rotationLength {{
                    length
                    unit
                }}
                participants {{
                    user {{
                        username
                        name
                    }}
                }}
            }}
        }}
    }}
    """
    return _graphql_request(query, variables)

# --- Mutation.oncallScheduleCreate ---
@mcp.tool()
def oncall_schedule_create(
    name: str,
    project_path: str,
    timezone: str,
    client_mutation_id: Optional[str] = None,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Creates a new on-call schedule in a GitLab project.

    Args:
        name (str): Name of the on-call schedule.
        project_path (str): Project to create the on-call schedule in.
        timezone (str): Timezone of the on-call schedule.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        description (Optional[str]): Description of the on-call schedule.
    """
    query = """
    mutation OncallScheduleCreate($input: OncallScheduleCreateInput!) {
      oncallScheduleCreate(input: $input) {
        clientMutationId
        errors
        oncallSchedule {
          id
          name
          description
          timezone
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "name": name,
            "projectPath": project_path,
            "timezone": timezone,
        }
    }
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id
    if description is not None:
        variables["input"]["description"] = description

    return _graphql_request(query, variables)

# --- Mutation.oncallScheduleDestroy ---
@mcp.tool()
def oncall_schedule_destroy(
    iid: str,
    project_path: str,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Destroys an on-call schedule in a project.

    Args:
        iid (str): On-call schedule internal ID to remove.
        project_path (str): Project to remove the on-call schedule from.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation OncallScheduleDestroy($input: OncallScheduleDestroyInput!) {
      oncallScheduleDestroy(input: $input) {
        clientMutationId
        errors
        oncallSchedule {
          id
          name
          description
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "iid": iid,
            "projectPath": project_path,
        }
    }
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.oncallScheduleUpdate ---
@mcp.tool()
def oncall_schedule_update(
    iid: str,
    project_path: str,
    client_mutation_id: Optional[str] = None,
    description: Optional[str] = None,
    name: Optional[str] = None,
    timezone: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Updates an existing on-call schedule in a GitLab project.

    Args:
        iid (str): On-call schedule internal ID to update.
        project_path (str): Project to update the on-call schedule in (e.g., 'group/project').
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        description (Optional[str]): Description of the on-call schedule.
        name (Optional[str]): Name of the on-call schedule.
        timezone (Optional[str]): Timezone of the on-call schedule.
    """
    query = """
    mutation OncallScheduleUpdate($input: OncallScheduleUpdateInput!) {
      oncallScheduleUpdate(input: $input) {
        clientMutationId
        errors
        oncallSchedule {
          id
          iid
          name
          description
          timezone
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "iid": iid,
            "projectPath": project_path,
        }
    }
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id
    if description is not None:
        variables["input"]["description"] = description
    if name is not None:
        variables["input"]["name"] = name
    if timezone is not None:
        variables["input"]["timezone"] = timezone

    return _graphql_request(query, variables)

# --- Mutation.pagesMarkOnboardingComplete ---
@mcp.tool()
def pages_mark_onboarding_complete(
    project_path: str,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Marks the Pages onboarding process as complete for a project.

    Args:
        project_path (str): Full path of the project.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation PagesMarkOnboardingComplete($clientMutationId: String, $projectPath: ID!) {
      pagesMarkOnboardingComplete(input: { clientMutationId: $clientMutationId, projectPath: $projectPath }) {
        clientMutationId
        errors
        onboardingComplete
      }
    }
    """
    variables: Dict[str, Any] = {
        "projectPath": project_path,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.pipelineCancel ---
@mcp.tool()
def pipeline_cancel(id: str, client_mutation_id: Optional[str] = None) -> Dict[str, Any]:
    """Cancels a specific pipeline.

    Args:
        id (str): ID of the pipeline to mutate.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
        mutation PipelineCancel($input: PipelineCancelInput!) {
            pipelineCancel(input: $input) {
                clientMutationId
                errors
            }
        }
    """
    variables = {
        "input": {
            "id": id,
        }
    }
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.pipelineDestroy ---
@mcp.tool()
def pipeline_destroy(id: str, client_mutation_id: Optional[str] = None) -> Dict[str, Any]:
    """Destroys a CI pipeline.

    Args:
        id (str): ID of the pipeline to mutate.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation PipelineDestroy($id: CiPipelineID!, $clientMutationId: String) {
      pipelineDestroy(input: {
        id: $id,
        clientMutationId: $clientMutationId
      }) {
        clientMutationId
        errors
      }
    }
    """
    variables = {
        "id": id,
        "clientMutationId": client_mutation_id,
    }
    return _graphql_request(query, variables)

# --- Mutation.pipelineRetry ---
@mcp.tool()
def pipeline_retry(id: str, client_mutation_id: Optional[str] = None) -> Dict[str, Any]:
    """Retries a GitLab CI/CD pipeline.

    Args:
        id (str): ID of the pipeline to mutate.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation PipelineRetry($id: CiPipelineID!, $clientMutationId: String) {
      pipelineRetry(input: { id: $id, clientMutationId: $clientMutationId }) {
        clientMutationId
        errors
        pipeline {
          id
          status
          duration
          createdAt
          updatedAt
          ref
          sha
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "id": id,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id
    return _graphql_request(query, variables)

# --- Mutation.pipelineScheduleCreate ---
@mcp.tool()
def pipeline_schedule_create(
    cron: str,
    description: str,
    project_path: str,
    ref: str,
    active: Optional[bool] = None,
    client_mutation_id: Optional[str] = None,
    cron_timezone: Optional[str] = None,
    variables_input: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Creates a new pipeline schedule for a project.

    Args:
        cron (str): Cron expression of the pipeline schedule.
        description (str): Description of the pipeline schedule.
        project_path (str): Full path of the project the pipeline schedule is associated with.
        ref (str): Ref of the pipeline schedule.
        active (Optional[bool]): Indicates if the pipeline schedule should be active or not.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        cron_timezone (Optional[str]): Cron time zone supported by ActiveSupport::TimeZone.
        variables_input (Optional[List[Dict[str, Any]]]): Variables for the pipeline schedule.
    """
    query = """
    mutation PipelineScheduleCreate(
      $active: Boolean
      $clientMutationId: String
      $cron: String!
      $cronTimezone: String
      $description: String!
      $projectPath: ID!
      $ref: String!
      $variables: [PipelineScheduleVariableInput!]
    ) {
      pipelineScheduleCreate(input: {
        active: $active
        clientMutationId: $clientMutationId
        cron: $cron
        cronTimezone: $cronTimezone
        description: $description
        projectPath: $projectPath
        ref: $ref
        variables: $variables
      }) {
        clientMutationId
        errors
        pipelineSchedule {
          id
          description
          cron
          ref
          active
          nextRunAt
          owner {
            id
            username
          }
        }
      }
    }
    """
    variables = {
        "cron": cron,
        "description": description,
        "projectPath": project_path,
        "ref": ref,
    }
    if active is not None:
        variables["active"] = active
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id
    if cron_timezone is not None:
        variables["cronTimezone"] = cron_timezone
    if variables_input is not None:
        variables["variables"] = variables_input

    return _graphql_request(query, variables)

# --- Mutation.pipelineScheduleDelete ---
@mcp.tool()
def pipeline_schedule_delete(id: str, client_mutation_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Deletes a pipeline schedule.

    Args:
        id (str): ID of the pipeline schedule to mutate.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
        mutation PipelineScheduleDelete($id: CiPipelineScheduleID!, $clientMutationId: String) {
            pipelineScheduleDelete(input: { id: $id, clientMutationId: $clientMutationId }) {
                clientMutationId
                errors
            }
        }
    """
    variables: Dict[str, Any] = {
        "id": id,
        "clientMutationId": client_mutation_id,
    }
    return _graphql_request(query, variables)

# --- Mutation.pipelineSchedulePlay ---
@mcp.tool()
def pipeline_schedule_play(id: str, client_mutation_id: Optional[str] = None) -> Dict[str, Any]:
    """Play a pipeline schedule.

    Args:
        id (str): ID of the pipeline schedule to mutate.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation PipelineSchedulePlay($id: CiPipelineScheduleID!, $clientMutationId: String) {
      pipelineSchedulePlay(input: { id: $id, clientMutationId: $clientMutationId }) {
        clientMutationId
        errors
        pipelineSchedule {
          id
          ref
          cron
          active
          description
          nextRunAt
          owner {
            id
            username
          }
        }
      }
    }
    """
    variables: Dict[str, Any] = {"id": id}
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.pipelineScheduleTakeOwnership ---
@mcp.tool()
def pipeline_schedule_take_ownership(id: str, client_mutation_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Takes ownership of a pipeline schedule.

    Args:
        id: ID of the pipeline schedule to mutate.
        client_mutation_id: A unique identifier for the client performing the mutation.
    """
    query = """
    mutation PipelineScheduleTakeOwnership($id: CiPipelineScheduleID!, $clientMutationId: String) {
      pipelineScheduleTakeOwnership(input: { id: $id, clientMutationId: $clientMutationId }) {
        clientMutationId
        errors
        pipelineSchedule {
          id
          description
          ref
          cron
          active
          nextRunAt
          owner {
            id
            username
          }
        }
      }
    }
    """
    variables = {
        "id": id,
        "clientMutationId": client_mutation_id,
    }
    return _graphql_request(query, variables)

# --- Mutation.projectCiCdSettingsUpdate ---
@mcp.tool()
def project_ci_cd_settings_update(
    full_path: str,
    client_mutation_id: Optional[str] = None,
    inbound_job_token_scope_enabled: Optional[bool] = None,
    job_token_scope_enabled: Optional[bool] = None,
    keep_latest_artifact: Optional[bool] = None,
    merge_pipelines_enabled: Optional[bool] = None,
    merge_trains_enabled: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Updates the CI/CD settings for a project.

    Args:
        full_path (str): Full Path of the project the settings belong to.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        inbound_job_token_scope_enabled (Optional[bool]): Indicates CI/CD job tokens generated in other projects have restricted access to this project.
        job_token_scope_enabled (Optional[bool]): Indicates CI/CD job tokens generated in this project have restricted access to other projects.
        keep_latest_artifact (Optional[bool]): Indicates if the latest artifact should be kept for this project.
        merge_pipelines_enabled (Optional[bool]): Indicates if merge pipelines are enabled for the project.
        merge_trains_enabled (Optional[bool]): Indicates if merge trains are enabled for the project.
    """
    variables = {
        "fullPath": full_path,
    }
    input_fields = []
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id
        input_fields.append("clientMutationId: $clientMutationId")
    if inbound_job_token_scope_enabled is not None:
        variables["inboundJobTokenScopeEnabled"] = inbound_job_token_scope_enabled
        input_fields.append("inboundJobTokenScopeEnabled: $inboundJobTokenScopeEnabled")
    if job_token_scope_enabled is not None:
        variables["jobTokenScopeEnabled"] = job_token_scope_enabled
        input_fields.append("jobTokenScopeEnabled: $jobTokenScopeEnabled")
    if keep_latest_artifact is not None:
        variables["keepLatestArtifact"] = keep_latest_artifact
        input_fields.append("keepLatestArtifact: $keepLatestArtifact")
    if merge_pipelines_enabled is not None:
        variables["mergePipelinesEnabled"] = merge_pipelines_enabled
        input_fields.append("mergePipelinesEnabled: $mergePipelinesEnabled")
    if merge_trains_enabled is not None:
        variables["mergeTrainsEnabled"] = merge_trains_enabled
        input_fields.append("mergeTrainsEnabled: $mergeTrainsEnabled")

    input_graphql_str = ", ".join(input_fields)

    query = f"""
    mutation ProjectCiCdSettingsUpdateMutation($fullPath: ID!, {input_graphql_str.replace(':', ': ')}${{", " if input_fields else ""}}) {{
      projectCiCdSettingsUpdate(input: {{ fullPath: $fullPath, {input_graphql_str} }}) {{
        ciCdSettings {{
          id
          inboundJobTokenScopeEnabled
          jobTokenScopeEnabled
          keepLatestArtifact
          mergePipelinesEnabled
          mergeTrainsEnabled
        }}
        clientMutationId
        errors
      }}
    }}
    """
    return _graphql_request(query, variables)

# --- Mutation.projectInitializeProductAnalytics ---
@mcp.tool()
def project_initialize_product_analytics(
    project_path: str, client_mutation_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Initializes product analytics for a project.

    Args:
        project_path (str): Full path of the project to initialize.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation ProjectInitializeProductAnalytics($projectPath: ID!, $clientMutationId: String) {
      projectInitializeProductAnalytics(input: {
        projectPath: $projectPath,
        clientMutationId: $clientMutationId
      }) {
        clientMutationId
        errors
        project {
          id
          fullPath
          name
          description
          webUrl
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "projectPath": project_path,
        "clientMutationId": client_mutation_id,
    }
    return _graphql_request(query, variables)

# --- Mutation.projectSetComplianceFramework ---
@mcp.tool()
def project_set_compliance_framework(
    project_id: str,
    compliance_framework_id: Optional[str] = None,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Assign (or unset) a compliance framework to a project.

    Args:
        project_id (str): ID of the project to change the compliance framework of.
        compliance_framework_id (Optional[str]): ID of the compliance framework to assign to the project. Set to `None` to unset.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation ProjectSetComplianceFramework(
      $projectId: ProjectID!
      $complianceFrameworkId: ComplianceManagementFrameworkID
      $clientMutationId: String
    ) {
      projectSetComplianceFramework(input: {
        projectId: $projectId
        complianceFrameworkId: $complianceFrameworkId
        clientMutationId: $clientMutationId
      }) {
        clientMutationId
        errors
        project {
          id
          name
          fullPath
          description
          complianceFramework {
            id
            name
            description
          }
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "projectId": project_id,
        "complianceFrameworkId": compliance_framework_id, # Can be null to unset
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.projectSetLocked ---
@mcp.tool()
def project_set_locked(
    file_path: str,
    lock: bool,
    project_path: str,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Sets the locked status for a specific file path within a project.

    Args:
        file_path: Full path to the file.
        lock: Whether or not to lock the file path.
        project_path: Full path of the project to mutate.
        client_mutation_id: A unique identifier for the client performing the mutation.
    """
    query = """
    mutation ProjectSetLockedMutation($input: ProjectSetLockedInput!) {
      projectSetLocked(input: $input) {
        clientMutationId
        errors
        project {
          id
          fullPath
          name
          webUrl
          description
          visibility
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "filePath": file_path,
            "lock": lock,
            "projectPath": project_path,
        }
    }
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.prometheusIntegrationCreate ---
@mcp.tool()
def prometheus_integration_create(
    active: bool,
    api_url: str,
    project_path: str,
    client_mutation_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Creates a new Prometheus integration for a GitLab project.

    Args:
        active (bool): Whether the integration is receiving alerts.
        api_url (str): Endpoint at which Prometheus can be queried.
        project_path (str): Project to create the integration in.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation PrometheusIntegrationCreate($input: PrometheusIntegrationCreateInput!) {
      prometheusIntegrationCreate(input: $input) {
        clientMutationId
        errors
        integration {
          id
          name
          apiUrl
          active
          createdAt
          updatedAt
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "active": active,
            "apiUrl": api_url,
            "projectPath": project_path,
        }
    }
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.prometheusIntegrationResetToken ---
@mcp.tool()
def prometheus_integration_reset_token(
    id: str, client_mutation_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Resets the token for a Prometheus integration.

    Args:
        id: ID of the integration to mutate.
        client_mutation_id: A unique identifier for the client performing the mutation.
    """
    query = """
    mutation PrometheusIntegrationResetToken($input: PrometheusIntegrationResetTokenInput!) {
      prometheusIntegrationResetToken(input: $input) {
        clientMutationId
        errors
        integration {
          id
          type
          name
          active
          apiUrl
          token
          endpointUrl
        }
      }
    }
    """
    variables: Dict[str, Any] = {"input": {"id": id}}
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.prometheusIntegrationUpdate ---
@mcp.tool()
def prometheus_integration_update(
    integration_id: str,
    active: Optional[bool] = None,
    api_url: Optional[str] = None,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Updates an existing Prometheus integration.

    Args:
        integration_id (str): ID of the integration to mutate.
        active (Optional[bool]): Whether the integration is receiving alerts.
        api_url (Optional[str]): Endpoint at which Prometheus can be queried.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation PrometheusIntegrationUpdate($input: PrometheusIntegrationUpdateInput!) {
      prometheusIntegrationUpdate(input: $input) {
        clientMutationId
        errors
        integration {
          id
          apiUrl
          active
          name
          token
          createdAt
          updatedAt
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "id": integration_id,
        }
    }
    if active is not None:
        variables["input"]["active"] = active
    if api_url is not None:
        variables["input"]["apiUrl"] = api_url
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.promoteToEpic ---
@mcp.tool()
def promote_to_epic(
    iid: str,
    project_path: str,
    client_mutation_id: Optional[str] = None,
    group_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Promotes an issue to an epic.

    Args:
        iid: IID of the issue to mutate.
        project_path: Project the issue to mutate is in.
        client_mutation_id: A unique identifier for the client performing the mutation.
        group_path: Group the promoted epic will belong to.
    """
    query = """
    mutation PromoteToEpic($input: PromoteToEpicInput!) {
      promoteToEpic(input: $input) {
        clientMutationId
        epic {
          id
          iid
          title
          description
          webUrl
          group {
            id
            fullPath
            name
          }
        }
        issue {
          id
          iid
          title
          webUrl
          project {
            id
            fullPath
            name
          }
        }
        errors
      }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "iid": iid,
            "projectPath": project_path,
        }
    }
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id
    if group_path is not None:
        variables["input"]["groupPath"] = group_path

    return _graphql_request(query, variables)

# --- Mutation.releaseAssetLinkCreate ---
@mcp.tool()
def release_asset_link_create(
    name: str,
    project_path: str,
    tag_name: str,
    url: str,
    client_mutation_id: Optional[str] = None,
    direct_asset_path: Optional[str] = None,
    link_type: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Creates a new asset link for a release.

    Args:
        name (str): Name of the asset link.
        project_path (str): Full path of the project the asset link is associated with.
        tag_name (str): Name of the associated release's tag.
        url (str): URL of the asset link.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        direct_asset_path (Optional[str]): Relative path for a direct asset link.
        link_type (Optional[str]): Type of the asset link (e.g., 'OTHER', 'RUNBOOK', 'PACKAGE').
    """
    query = """
    mutation ReleaseAssetLinkCreate($input: ReleaseAssetLinkCreateInput!) {
      releaseAssetLinkCreate(input: $input) {
        clientMutationId
        errors
        link {
          id
          name
          url
          linkType
          directAssetPath
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "name": name,
            "projectPath": project_path,
            "tagName": tag_name,
            "url": url,
        }
    }
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id
    if direct_asset_path is not None:
        variables["input"]["directAssetPath"] = direct_asset_path
    if link_type is not None:
        variables["input"]["linkType"] = link_type

    return _graphql_request(query, variables)

# --- Mutation.releaseAssetLinkDelete ---
@mcp.tool()
def release_asset_link_delete(
    release_asset_link_id: str,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Deletes a release asset link.

    Args:
        release_asset_link_id: ID of the release asset link to delete.
        client_mutation_id: A unique identifier for the client performing the mutation.
    """
    query = """
    mutation ReleaseAssetLinkDelete($id: ReleasesLinkID!, $clientMutationId: String) {
      releaseAssetLinkDelete(input: { id: $id, clientMutationId: $clientMutationId }) {
        clientMutationId
        errors
        link {
          id
          url
          name
          linkType
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "id": release_asset_link_id,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.releaseAssetLinkUpdate ---
@mcp.tool()
def release_asset_link_update(
    id: str,
    client_mutation_id: Optional[str] = None,
    direct_asset_path: Optional[str] = None,
    link_type: Optional[str] = None,
    name: Optional[str] = None,
    url: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Updates an existing release asset link in GitLab.

    Args:
        id (str): ID of the release asset link to update.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        direct_asset_path (Optional[str]): Relative path for a direct asset link.
        link_type (Optional[str]): Type of the asset link (e.g., 'OTHER', 'RUNBOOK', 'PACKAGE').
        name (Optional[str]): Name of the asset link.
        url (Optional[str]): URL of the asset link.
    """
    query = """
    mutation ReleaseAssetLinkUpdate(
        $id: ReleasesLinkID!,
        $clientMutationId: String,
        $directAssetPath: String,
        $linkType: ReleaseAssetLinkType,
        $name: String,
        $url: String
    ) {
        releaseAssetLinkUpdate(input: {
            id: $id,
            clientMutationId: $clientMutationId,
            directAssetPath: $directAssetPath,
            linkType: $linkType,
            name: $name,
            url: $url
        }) {
            clientMutationId
            errors
            link {
                id
                name
                url
                linkType
                directAssetPath
            }
        }
    }
    """
    variables: Dict[str, Any] = {
        "id": id,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id
    if direct_asset_path is not None:
        variables["directAssetPath"] = direct_asset_path
    if link_type is not None:
        variables["linkType"] = link_type
    if name is not None:
        variables["name"] = name
    if url is not None:
        variables["url"] = url

    return _graphql_request(query, variables)

# --- Mutation.releaseCreate ---
@mcp.tool()
def release_create(
    project_path: str,
    tag_name: str,
    assets: Optional[Dict[str, Any]] = None,
    client_mutation_id: Optional[str] = None,
    description: Optional[str] = None,
    milestones: Optional[List[List[str]]] = None,
    name: Optional[str] = None,
    ref: Optional[str] = None,
    released_at: Optional[str] = None,
    tag_message: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Creates a new release for a project.

    Args:
        project_path: Full path of the project the release is associated with.
        tag_name: Name of the tag to associate with the release.
        assets: Assets associated to the release.
        client_mutation_id: A unique identifier for the client performing the mutation.
        description: Description (release notes) of the release.
        milestones: Title of each milestone the release is associated with.
        name: Name of the release.
        ref: Commit SHA or branch name to use if creating a new tag.
        released_at: Date and time for the release in ISO 8601 format.
        tag_message: Message to use if creating a new annotated tag.
    """
    query = """
    mutation ReleaseCreate(
      $assets: ReleaseAssetsInput
      $clientMutationId: String
      $description: String
      $milestones: [[String!]]
      $name: String
      $projectPath: ID!
      $ref: String
      $releasedAt: Time
      $tagMessage: String
      $tagName: String!
    ) {
      releaseCreate(input: {
        assets: $assets
        clientMutationId: $clientMutationId
        description: $description
        milestones: $milestones
        name: $name
        projectPath: $projectPath
        ref: $ref
        releasedAt: $releasedAt
        tagMessage: $tagMessage
        tagName: $tagName
      }) {
        clientMutationId
        errors
        release {
          id
          name
          tagName
          description
          ref
          releasedAt
          tag {
            id
            name
            message
          }
          assets {
            count
            sources {
              nodes {
                url
                format
                type
              }
            }
            links {
              nodes {
                id
                name
                url
                linkType
                external
              }
            }
          }
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "projectPath": project_path,
        "tagName": tag_name,
    }
    if assets is not None:
        variables["assets"] = assets
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id
    if description is not None:
        variables["description"] = description
    if milestones is not None:
        variables["milestones"] = milestones
    if name is not None:
        variables["name"] = name
    if ref is not None:
        variables["ref"] = ref
    if released_at is not None:
        variables["releasedAt"] = released_at
    if tag_message is not None:
        variables["tagMessage"] = tag_message

    return _graphql_request(query, variables)

# --- Mutation.releaseDelete ---
@mcp.tool()
def release_delete(
    project_path: str,
    tag_name: str,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Deletes a release associated with a project and tag name.

    Args:
        project_path (str): Full path of the project the release is associated with.
        tag_name (str): Name of the tag associated with the release to delete.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation ReleaseDelete(
        $projectPath: ID!,
        $tagName: String!,
        $clientMutationId: String
    ) {
        releaseDelete(input: {
            projectPath: $projectPath,
            tagName: $tagName,
            clientMutationId: $clientMutationId
        }) {
            clientMutationId
            errors
            release {
                id
                tagName
                description
                releasedAt
            }
        }
    }
    """
    variables: Dict[str, Any] = {
        "projectPath": project_path,
        "tagName": tag_name,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.releaseUpdate ---
@mcp.tool()
def release_update(
    project_path: str,
    tag_name: str,
    client_mutation_id: Optional[str] = None,
    description: Optional[str] = None,
    milestones: Optional[List[List[str]]] = None,
    name: Optional[str] = None,
    released_at: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Updates an existing GitLab release.

    Args:
        project_path (str): Full path of the project the release is associated with.
        tag_name (str): Name of the tag associated with the release.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        description (Optional[str]): Description (release notes) of the release.
        milestones (Optional[List[List[str]]]): Title of each milestone the release is associated with.
        name (Optional[str]): Name of the release.
        released_at (Optional[str]): Release date (ISO 8601 format expected).
    """
    query = """
    mutation ReleaseUpdate($input: ReleaseUpdateInput!) {
      releaseUpdate(input: $input) {
        clientMutationId
        errors
        release {
          id
          name
          tagName
          description
          milestones {
            nodes {
              id
              title
            }
          }
          releasedAt
          project {
            id
            fullPath
          }
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "projectPath": project_path,
            "tagName": tag_name,
        }
    }
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id
    if description is not None:
        variables["input"]["description"] = description
    if milestones is not None:
        variables["input"]["milestones"] = milestones
    if name is not None:
        variables["input"]["name"] = name
    if released_at is not None:
        variables["input"]["releasedAt"] = released_at

    return _graphql_request(query, variables)

# --- Mutation.removeProjectFromSecurityDashboard ---
@mcp.tool()
def remove_project_from_security_dashboard(
    id: str,
    client_mutation_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Removes a project from the Instance Security Dashboard.

    Args:
        id: ID of the project to remove from the Instance Security Dashboard.
        client_mutation_id: A unique identifier for the client performing the mutation.
    """
    query = """
    mutation RemoveProjectFromSecurityDashboard($id: ProjectID!, $clientMutationId: String) {
      removeProjectFromSecurityDashboard(input: { id: $id, clientMutationId: $clientMutationId }) {
        clientMutationId
        errors
      }
    }
    """
    variables = {
        "id": id,
        "clientMutationId": client_mutation_id,
    }
    return _graphql_request(query, variables=variables)

# --- Mutation.repositionImageDiffNote ---
@mcp.tool()
def reposition_image_diff_note(
    note_id: str,
    position: Dict[str, Any],
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Reposition a DiffNote on an image.

    Args:
        note_id (str): Global ID of the DiffNote to update.
        position (Dict[str, Any]): Position of this note on a diff.
            Expected keys include 'x', 'y', 'width', 'height', 'positionType', and 'paths'.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation repositionImageDiffNoteMutation(
      $id: DiffNoteID!,
      $position: UpdateDiffImagePositionInput!,
      $clientMutationId: String
    ) {
      repositionImageDiffNote(input: {
        id: $id,
        position: $position,
        clientMutationId: $clientMutationId
      }) {
        clientMutationId
        errors
        note {
          id
          body
          position {
            x
            y
            width
            height
            positionType
            paths {
              oldPath
              newPath
            }
          }
          url
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "id": note_id,
        "position": position,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.runnerDelete ---
@mcp.tool()
def runner_delete(id: str, client_mutation_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Deletes a GitLab CI/CD runner.

    Args:
        id: ID of the runner to delete.
        client_mutation_id: A unique identifier for the client performing the mutation.
    """
    query = """
    mutation RunnerDelete($id: CiRunnerID!, $clientMutationId: String) {
      runnerDelete(input: { id: $id, clientMutationId: $clientMutationId }) {
        clientMutationId
        errors
      }
    }
    """
    variables: Dict[str, Any] = {
        "id": id,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.runnerUpdate ---
@mcp.tool()
def runner_update(
    id: str,
    access_level: Optional[str] = None,
    active: Optional[bool] = None,
    associated_projects: Optional[List[str]] = None,
    client_mutation_id: Optional[str] = None,
    description: Optional[str] = None,
    locked: Optional[bool] = None,
    maintenance_note: Optional[str] = None,
    maximum_timeout: Optional[int] = None,
    paused: Optional[bool] = None,
    private_projects_minutes_cost_factor: Optional[float] = None,
    public_projects_minutes_cost_factor: Optional[float] = None,
    run_untagged: Optional[bool] = None,
    tag_list: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Updates the properties of an existing GitLab CI runner.

    Args:
        id: ID of the runner to update.
        access_level: Access level of the runner.
        active: **Deprecated:** This was renamed. Please use `paused`. Deprecated in 14.8.
        associated_projects: Projects associated with the runner. Available only for project runners.
        client_mutation_id: A unique identifier for the client performing the mutation.
        description: Description of the runner.
        locked: Indicates the runner is locked.
        maintenance_note: Runner's maintenance notes.
        maximum_timeout: Maximum timeout (in seconds) for jobs processed by the runner.
        paused: Indicates the runner is not allowed to receive jobs.
        private_projects_minutes_cost_factor: Private projects' "minutes cost factor" associated with the runner (GitLab.com only).
        public_projects_minutes_cost_factor: Public projects' "minutes cost factor" associated with the runner (GitLab.com only).
        run_untagged: Indicates the runner is able to run untagged jobs.
        tag_list: Tags associated with the runner.
    """
    variables: Dict[str, Any] = {"id": id}
    if access_level is not None:
        variables["accessLevel"] = access_level
    if active is not None:
        variables["active"] = active
    if associated_projects is not None:
        variables["associatedProjects"] = associated_projects
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id
    if description is not None:
        variables["description"] = description
    if locked is not None:
        variables["locked"] = locked
    if maintenance_note is not None:
        variables["maintenanceNote"] = maintenance_note
    if maximum_timeout is not None:
        variables["maximumTimeout"] = maximum_timeout
    if paused is not None:
        variables["paused"] = paused
    if private_projects_minutes_cost_factor is not None:
        variables["privateProjectsMinutesCostFactor"] = private_projects_minutes_cost_factor
    if public_projects_minutes_cost_factor is not None:
        variables["publicProjectsMinutesCostFactor"] = public_projects_minutes_cost_factor
    if run_untagged is not None:
        variables["runUntagged"] = run_untagged
    if tag_list is not None:
        variables["tagList"] = tag_list

    query = """
    mutation RunnerUpdate($input: RunnerUpdateInput!) {
      runnerUpdate(input: $input) {
        clientMutationId
        errors
        runner {
          id
          description
          paused
          runUntagged
          locked
          accessLevel
          tagList
          maintenanceNote
          maximumTimeout
          privateProjectsMinutesCostFactor
          publicProjectsMinutesCostFactor
        }
      }
    }
    """
    return _graphql_request(query, variables={"input": variables})

# --- Mutation.runnersRegistrationTokenReset ---
@mcp.tool()
def runners_registration_token_reset(
    type: str,
    client_mutation_id: Optional[str] = None,
    id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Resets the registration token for a GitLab runner.

    Args:
        type (str): Scope of the object to reset the token for.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        id (Optional[str]): ID of the project or group to reset the token for. Omit if resetting instance runner token.
    """
    query = """
    mutation RunnersRegistrationTokenReset(
      $clientMutationId: String
      $id: ID
      $type: CiRunnerType!
    ) {
      runnersRegistrationTokenReset(input: {
        clientMutationId: $clientMutationId
        id: $id
        type: $type
      }) {
        clientMutationId
        errors
        token
      }
    }
    """
    variables: Dict[str, Any] = {
        "type": type,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id
    if id is not None:
        variables["id"] = id

    return _graphql_request(query, variables)

# --- Mutation.savedReplyCreate ---
@mcp.tool()
def saved_reply_create(
    content: str,
    name: str,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Creates a new saved reply.

    Args:
        content: Content of the saved reply.
        name: Name of the saved reply.
        client_mutation_id: A unique identifier for the client performing the mutation.
    """
    query = """
    mutation SavedReplyCreate($content: String!, $name: String!, $clientMutationId: String) {
      savedReplyCreate(input: {
        content: $content,
        name: $name,
        clientMutationId: $clientMutationId
      }) {
        clientMutationId
        errors
        savedReply {
          id
          name
          content
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "content": content,
        "name": name,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.savedReplyDestroy ---
@mcp.tool()
def saved_reply_destroy(
    id: str,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Deletes a saved reply.

    Args:
        id (str): Global ID of the saved reply to destroy.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
        mutation SavedReplyDestroy($id: UsersSavedReplyID!, $clientMutationId: String) {
            savedReplyDestroy(input: { id: $id, clientMutationId: $clientMutationId }) {
                clientMutationId
                errors
                savedReply {
                    id
                    name
                    content
                }
            }
        }
    """
    variables: Dict[str, Any] = {
        "id": id,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.savedReplyUpdate ---
@mcp.tool()
def saved_reply_update(
    content: str,
    saved_reply_id: str,
    name: str,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Updates an existing saved reply.

    Args:
        content (str): Content of the saved reply.
        saved_reply_id (str): Global ID of the saved reply.
        name (str): Name of the saved reply.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation savedReplyUpdate(
      $clientMutationId: String
      $content: String!
      $id: UsersSavedReplyID!
      $name: String!
    ) {
      savedReplyUpdate(input: {
        clientMutationId: $clientMutationId
        content: $content
        id: $id
        name: $name
      }) {
        clientMutationId
        errors
        savedReply {
          id
          name
          content
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "content": content,
        "id": saved_reply_id,
        "name": name,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.scanExecutionPolicyCommit ---
@mcp.tool()
def scan_execution_policy_commit(
    operation_mode: str,
    policy_yaml: str,
    client_mutation_id: Optional[str] = None,
    full_path: Optional[str] = None,
    name: Optional[str] = None,
    project_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Commits the policy YAML content to a security policy project.

    Args:
        operation_mode (str): Changes the operation mode.
        policy_yaml (str): YAML snippet of the policy.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        full_path (Optional[str]): Full path of the project.
        name (Optional[str]): Name of the policy. If the name is null, the `name` field from `policy_yaml` is used.
        project_path (Optional[str]): Deprecated: Use `fullPath`.
    """
    query = """
    mutation ScanExecutionPolicyCommit(
      $clientMutationId: String
      $fullPath: String
      $name: String
      $operationMode: MutationOperationMode!
      $policyYaml: String!
      $projectPath: ID
    ) {
      scanExecutionPolicyCommit(input: {
        clientMutationId: $clientMutationId
        fullPath: $fullPath
        name: $name
        operationMode: $operationMode
        policyYaml: $policyYaml
        projectPath: $projectPath
      }) {
        branch
        clientMutationId
        errors
      }
    }
    """
    variables: Dict[str, Any] = {
        "operationMode": operation_mode,
        "policyYaml": policy_yaml,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id
    if full_path is not None:
        variables["fullPath"] = full_path
    if name is not None:
        variables["name"] = name
    if project_path is not None:
        variables["projectPath"] = project_path

    return _graphql_request(query, variables)

# --- Mutation.securityFindingCreateIssue ---
@mcp.tool()
def security_finding_create_issue(
    project_id: str,
    uuid: str,
    client_mutation_id: Optional[str] = None
) -> Dict[str, Any]:
    """Creates an issue from a security finding.

    Args:
        project_id: ID of the project to attach the issue to.
        uuid: UUID of the security finding to be used to create an issue.
        client_mutation_id: A unique identifier for the client performing the mutation.
    """
    query = """
    mutation securityFindingCreateIssue($project: ProjectID!, $uuid: String!, $clientMutationId: String) {
      securityFindingCreateIssue(input: {
        project: $project,
        uuid: $uuid,
        clientMutationId: $clientMutationId
      }) {
        clientMutationId
        errors
        issue {
          id
          iid
          title
          webUrl
          state
          createdAt
          updatedAt
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "project": project_id,
        "uuid": uuid,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.securityFindingDismiss ---
@mcp.tool()
def security_finding_dismiss(
    uuid: str,
    comment: Optional[str] = None,
    dismissal_reason: Optional[str] = None,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Dismiss a security finding.

    Args:
        uuid: UUID of the finding to be dismissed.
        comment: Comment why finding should be dismissed.
        dismissal_reason: Reason why finding should be dismissed.
        client_mutation_id: A unique identifier for the client performing the mutation.
    """
    query = """
    mutation SecurityFindingDismiss($input: SecurityFindingDismissInput!) {
      securityFindingDismiss(input: $input) {
        clientMutationId
        errors
        uuid
      }
    }
    """
    variables = {
        "input": {
            "uuid": uuid
        }
    }
    if comment is not None:
        variables["input"]["comment"] = comment
    if dismissal_reason is not None:
        variables["input"]["dismissalReason"] = dismissal_reason
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.securityPolicyProjectAssign ---
@mcp.tool()
def security_policy_project_assign(
    full_path: str,
    security_policy_project_id: str,
    client_mutation_id: Optional[str] = None,
    project_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Assigns a security policy project to a given project or group.

    Args:
        full_path (str): Full path of the project or group.
        security_policy_project_id (str): ID of the security policy project.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        project_path (Optional[str]): Deprecated: Use `full_path`.
    """
    query = """
    mutation SecurityPolicyProjectAssign($input: SecurityPolicyProjectAssignInput!) {
        securityPolicyProjectAssign(input: $input) {
            clientMutationId
            errors
        }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "fullPath": full_path,
            "securityPolicyProjectId": security_policy_project_id,
        }
    }
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id
    if project_path is not None:
        variables["input"]["projectPath"] = project_path

    return _graphql_request(query, variables)

# --- Mutation.securityPolicyProjectCreate ---
@mcp.tool()
def security_policy_project_create(
    client_mutation_id: Optional[str] = None,
    full_path: Optional[str] = None,
    project_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Creates and assigns a security policy project for the given project.

    Args:
        client_mutation_id: A unique identifier for the client performing the mutation.
        full_path: Full path of the project or group.
        project_path: Deprecated: Use `fullPath`.
    """
    query = """
    mutation SecurityPolicyProjectCreate(
      $clientMutationId: String
      $fullPath: String
      $projectPath: ID
    ) {
      securityPolicyProjectCreate(input: {
        clientMutationId: $clientMutationId
        fullPath: $fullPath
        projectPath: $projectPath
      }) {
        clientMutationId
        errors
        project {
          id
          fullPath
          name
          description
          webUrl
          visibility
          createdAt
          updatedAt
        }
      }
    }
    """
    variables = {
        "clientMutationId": client_mutation_id,
        "fullPath": full_path,
        "projectPath": project_path,
    }
    return _graphql_request(query, variables)

# --- Mutation.securityPolicyProjectUnassign ---
@mcp.tool()
def security_policy_project_unassign(full_path: str, client_mutation_id: Optional[str] = None) -> Dict[str, Any]:
    """Unassigns the security policy project for a given project.

    Args:
        full_path: Full path of the project or group.
        client_mutation_id: A unique identifier for the client performing the mutation.
    """
    query = """
        mutation SecurityPolicyProjectUnassign($fullPath: String!, $clientMutationId: String) {
            securityPolicyProjectUnassign(input: { fullPath: $fullPath, clientMutationId: $clientMutationId }) {
                clientMutationId
                errors
            }
        }
    """
    variables: Dict[str, Any] = {
        "fullPath": full_path,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.securityTrainingUpdate ---
@mcp.tool()
def security_training_update(
    is_enabled: bool,
    project_path: str,
    provider_id: str,
    client_mutation_id: Optional[str] = None,
    is_primary: Optional[bool] = None,
) -> Dict[str, Any]:
    """Updates security training provider settings for a project.

    Args:
        is_enabled: Sets the training provider as enabled for the project.
        project_path: Full path of the project.
        provider_id: ID of the provider.
        client_mutation_id: A unique identifier for the client performing the mutation.
        is_primary: Sets the training provider as primary for the project.
    """
    query = """
    mutation SecurityTrainingUpdate($input: SecurityTrainingUpdateInput!) {
      securityTrainingUpdate(input: $input) {
        clientMutationId
        errors
        training {
          id
          name
          url
          isEnabled
          isPrimary
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "isEnabled": is_enabled,
            "projectPath": project_path,
            "providerId": provider_id,
        }
    }
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id
    if is_primary is not None:
        variables["input"]["isPrimary"] = is_primary

    return _graphql_request(query, variables)

# --- Mutation.terraformStateDelete ---
@mcp.tool()
def terraform_state_delete(id: str, client_mutation_id: Optional[str] = None) -> Dict[str, Any]:
    """Deletes a Terraform state.

    Args:
        id: Global ID of the Terraform state.
        client_mutation_id: A unique identifier for the client performing the mutation.
    """
    query = """
    mutation TerraformStateDelete($input: TerraformStateDeleteInput!) {
      terraformStateDelete(input: $input) {
        clientMutationId
        errors
      }
    }
    """
    variables: Dict[str, Any] = {"input": {"id": id}}
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id
    return _graphql_request(query, variables)

# --- Mutation.terraformStateLock ---
@mcp.tool()
def terraform_state_lock(id: str, client_mutation_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Locks a Terraform state.

    Args:
        id (str): Global ID of the Terraform state.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation TerraformStateLock($input: TerraformStateLockInput!) {
      terraformStateLock(input: $input) {
        clientMutationId
        errors
      }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "id": id,
        }
    }
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.terraformStateUnlock ---
@mcp.tool()
def terraform_state_unlock(id: str, client_mutation_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Unlocks a Terraform state.

    Args:
        id (str): Global ID of the Terraform state.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation TerraformStateUnlock($input: TerraformStateUnlockInput!) {
      terraformStateUnlock(input: $input) {
        clientMutationId
        errors
      }
    }
    """
    variables = {
        "input": {
            "id": id,
        }
    }
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.timelineEventCreate ---
@mcp.tool()
def timeline_event_create(
    incident_id: str,
    note: str,
    occurred_at: str,
    client_mutation_id: Optional[str] = None,
    timeline_event_tag_names: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Create a new timeline event for an incident.

    Args:
        incident_id: Incident ID of the timeline event.
        note: Text note of the timeline event.
        occurred_at: Timestamp of when the event occurred.
        client_mutation_id: A unique identifier for the client performing the mutation.
        timeline_event_tag_names: Tags for the incident timeline event.
    """
    query = """
    mutation TimelineEventCreate(
        $incidentId: IssueID!,
        $note: String!,
        $occurredAt: Time!,
        $clientMutationId: String,
        $timelineEventTagNames: [String!]
    ) {
        timelineEventCreate(input: {
            incidentId: $incidentId,
            note: $note,
            occurredAt: $occurredAt,
            clientMutationId: $clientMutationId,
            timelineEventTagNames: $timelineEventTagNames
        }) {
            clientMutationId
            errors
            timelineEvent {
                id
                note
                occurredAt
                timelineEventTags {
                    nodes {
                        id
                        name
                    }
                }
            }
        }
    }
    """
    variables: Dict[str, Any] = {
        "incidentId": incident_id,
        "note": note,
        "occurredAt": occurred_at,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id
    if timeline_event_tag_names is not None:
        variables["timelineEventTagNames"] = timeline_event_tag_names

    return _graphql_request(query, variables)

# --- Mutation.timelineEventDestroy ---
@mcp.tool()
def timeline_event_destroy(
    id: str,
    client_mutation_id: Optional[str] = None
) -> Dict[str, Any]:
    """Removes a timeline event.

    Args:
        id (str): Timeline event ID to remove.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation TimelineEventDestroy($input: TimelineEventDestroyInput!) {
      timelineEventDestroy(input: $input) {
        clientMutationId
        errors
        timelineEvent {
          id
          note
          # Add more fields from TimelineEventType if needed
          # e.g., occurredAt, action, author { username }
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "id": id
        }
    }
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.timelineEventPromoteFromNote ---
@mcp.tool()
def timeline_event_promote_from_note(note_id: str, client_mutation_id: Optional[str] = None) -> Dict[str, Any]:
    """Promotes a note to a timeline event.

    Args:
        note_id (str): The ID of the note from which to promote the timeline event.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation TimelineEventPromoteFromNote($input: TimelineEventPromoteFromNoteInput!) {
      timelineEventPromoteFromNote(input: $input) {
        clientMutationId
        errors
        timelineEvent {
          id
          action
          createdAt
          note {
            id
            body
          }
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "noteId": note_id
        }
    }
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.timelineEventTagCreate ---
@mcp.tool()
def timeline_event_tag_create(
    name: str,
    project_path: str,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Creates a new timeline event tag for a project.

    Args:
        name (str): Name of the tag.
        project_path (str): Project to create the timeline event tag in.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation TimelineEventTagCreate($name: String!, $projectPath: ID!, $clientMutationId: String) {
      timelineEventTagCreate(input: {
        name: $name,
        projectPath: $projectPath,
        clientMutationId: $clientMutationId
      }) {
        clientMutationId
        errors
        timelineEventTag {
          id
          name
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "name": name,
        "projectPath": project_path,
        "clientMutationId": client_mutation_id,
    }
    return _graphql_request(query, variables)

# --- Mutation.timelineEventUpdate ---
@mcp.tool()
def timeline_event_update(
    id: str,
    client_mutation_id: Optional[str] = None,
    note: Optional[str] = None,
    occurred_at: Optional[str] = None,
    timeline_event_tag_names: Optional[List[List[str]]] = None,
) -> Dict[str, Any]:
    """Updates an existing incident timeline event.

    Args:
        id (str): ID of the timeline event to update.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        note (Optional[str]): Text note of the timeline event.
        occurred_at (Optional[str]): Timestamp when the event occurred (ISO 8601 string).
        timeline_event_tag_names (Optional[List[List[str]]]): Tags for the incident timeline event.
    """
    query = """
    mutation TimelineEventUpdate($input: TimelineEventUpdateInput!) {
      timelineEventUpdate(input: $input) {
        clientMutationId
        errors
        timelineEvent {
          id
          note
          occurredAt
          author {
            username
            name
          }
          timelineEventTags {
            nodes {
              id
              name
            }
          }
          createdAt
          updatedAt
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "id": id,
        }
    }
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id
    if note is not None:
        variables["input"]["note"] = note
    if occurred_at is not None:
        variables["input"]["occurredAt"] = occurred_at
    if timeline_event_tag_names is not None:
        variables["input"]["timelineEventTagNames"] = timeline_event_tag_names

    return _graphql_request(query, variables)

# --- Mutation.timelogCreate ---
@mcp.tool()
def timelog_create(
    issuable_id: str,
    spent_at: str,
    summary: str,
    time_spent: str,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Creates a new timelog entry for an issuable.

    Args:
        issuable_id (str): Global ID of the issuable (Issue, WorkItem or MergeRequest).
        spent_at (str): When the time was spent (e.g., "YYYY-MM-DDTHH:MM:SSZ").
        summary (str): Summary of time spent.
        time_spent (str): Amount of time spent (e.g., "1h 30m").
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
        mutation TimelogCreate(
            $issuableId: IssuableID!,
            $spentAt: Time!,
            $summary: String!,
            $timeSpent: String!,
            $clientMutationId: String
        ) {
            timelogCreate(input: {
                issuableId: $issuableId,
                spentAt: $spentAt,
                summary: $summary,
                timeSpent: $timeSpent,
                clientMutationId: $clientMutationId
            }) {
                clientMutationId
                errors
                timelog {
                    id
                    spentAt
                    timeSpent
                    summary
                }
            }
        }
    """
    variables: Dict[str, Any] = {
        "issuableId": issuable_id,
        "spentAt": spent_at,
        "summary": summary,
        "timeSpent": time_spent,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.timelogDelete ---
@mcp.tool()
def timelog_delete(
    id: str,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Deletes a timelog entry.

    Args:
        id (str): Global ID of the timelog.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation TimelogDelete($id: TimelogID!, $clientMutationId: String) {
      timelogDelete(input: { id: $id, clientMutationId: $clientMutationId }) {
        clientMutationId
        errors
        timelog {
          id
          spentAt
          timeSpent
          summary
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "id": id,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.todoCreate ---
@mcp.tool()
def todo_create(
    target_id: str,
    client_mutation_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Creates a new to-do item for a given target.

    Args:
        target_id (str): Global ID of the to-do item's parent.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation TodoCreate($targetId: TodoableID!, $clientMutationId: String) {
      todoCreate(input: { targetId: $targetId, clientMutationId: $clientMutationId }) {
        clientMutationId
        errors
        todo {
          id
          state
          action
          targetType
          body
          project {
            id
            name
            fullPath
          }
          author {
            id
            username
          }
          createdAt
          updatedAt
        }
      }
    }
    """
    variables = {
        "targetId": target_id,
        "clientMutationId": client_mutation_id,
    }
    return _graphql_request(query, variables)

# --- Mutation.todoMarkDone ---
@mcp.tool()
def todo_mark_done(id: str, client_mutation_id: Optional[str] = None) -> Dict[str, Any]:
    """Marks a to-do item as done.

    Args:
        id (str): Global ID of the to-do item to mark as done.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
        mutation TodoMarkDoneMutation($id: TodoID!, $clientMutationId: String) {
            todoMarkDone(input: { id: $id, clientMutationId: $clientMutationId }) {
                clientMutationId
                errors
                todo {
                    id
                    state
                    action
                    targetType
                    author {
                        username
                    }
                    project {
                        id
                        name
                        fullPath
                    }
                    group {
                        id
                        name
                        fullPath
                    }
                }
            }
        }
    """
    variables = {
        "id": id,
        "clientMutationId": client_mutation_id,
    }
    variables = {k: v for k, v in variables.items() if v is not None}

    return _graphql_request(query, variables)

# --- Mutation.todoRestore ---
@mcp.tool()
def todo_restore(todo_id: str, client_mutation_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Restores a to-do item in GitLab.

    Args:
        todo_id (str): Global ID of the to-do item to restore.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation todoRestore($input: TodoRestoreInput!) {
      todoRestore(input: $input) {
        clientMutationId
        errors
        todo {
          id
          state
          action
          targetType
          body
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "id": todo_id,
        }
    }
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.todoRestoreMany ---
@mcp.tool()
def todo_restore_many(ids: List[str], client_mutation_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Restores multiple to-do items.

    Args:
        ids (List[str]): Global IDs of the to-do items to restore (maximum 50).
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation TodoRestoreMany($input: TodoRestoreManyInput!) {
      todoRestoreMany(input: $input) {
        clientMutationId
        errors
        todos {
          id
          state
          bodyHtml
          targetType
          action
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "ids": ids
        }
    }
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.todosMarkAllDone ---
@mcp.tool()
def todos_mark_all_done(
    client_mutation_id: Optional[str] = None,
    target_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Marks all pending to-do items as done for the current user or a specific target.

    Args:
        client_mutation_id: A unique identifier for the client performing the mutation.
        target_id: Global ID of the to-do item's parent (e.g., an Issue, MergeRequest, Design, or Epic).
                   If omitted, all pending to-do items of the current user are marked as done.
    """
    query = """
        mutation TodosMarkAllDoneMutation(
            $clientMutationId: String
            $targetId: TodoableID
        ) {
            todosMarkAllDone(input: {
                clientMutationId: $clientMutationId
                targetId: $targetId
            }) {
                clientMutationId
                errors
                todos {
                    id
                    state
                    action
                    body
                    targetType
                    createdAt
                }
            }
        }
    """
    variables = {}
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id
    if target_id is not None:
        variables["targetId"] = target_id

    return _graphql_request(query, variables)

# --- Mutation.updateAlertStatus ---
@mcp.tool()
def update_alert_status(
    iid: str,
    project_path: str,
    status: str,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Update the status of an alert in a project.

    Args:
        iid (str): IID of the alert to mutate.
        project_path (str): Project the alert to mutate is in.
        status (str): Status to set the alert.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    variables: Dict[str, Any] = {
        "iid": iid,
        "projectPath": project_path,
        "status": status,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id

    query = """
    mutation UpdateAlertStatus($iid: String!, $projectPath: ID!, $status: AlertManagementStatus!, $clientMutationId: String) {
      updateAlertStatus(input: {
        iid: $iid,
        projectPath: $projectPath,
        status: $status,
        clientMutationId: $clientMutationId
      }) {
        alert {
          id
          iid
          status
          title
          createdAt
        }
        issue {
          id
          iid
          title
          webUrl
        }
        todo {
          id
          body
          state
        }
        clientMutationId
        errors
      }
    }
    """
    return _graphql_request(query, variables=variables)

# --- Mutation.updateBoard ---
@mcp.tool()
def update_board(
    id: str,
    assignee_id: Optional[str] = None,
    client_mutation_id: Optional[str] = None,
    hide_backlog_list: Optional[bool] = None,
    hide_closed_list: Optional[bool] = None,
    iteration_cadence_id: Optional[str] = None,
    iteration_id: Optional[str] = None,
    label_ids: Optional[List[str]] = None,
    labels: Optional[List[str]] = None,
    milestone_id: Optional[str] = None,
    name: Optional[str] = None,
    weight: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Updates an existing GitLab board with new attributes.

    Args:
        id (str): Board global ID.
        assignee_id (Optional[str]): ID of user to be assigned to the board.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        hide_backlog_list (Optional[bool]): Whether or not backlog list is hidden.
        hide_closed_list (Optional[bool]): Whether or not closed list is hidden.
        iteration_cadence_id (Optional[str]): ID of iteration cadence to be assigned to the board.
        iteration_id (Optional[str]): ID of iteration to be assigned to the board.
        label_ids (Optional[List[str]]): IDs of labels to be added to the board.
        labels (Optional[List[str]]): Labels of the issue.
        milestone_id (Optional[str]): ID of milestone to be assigned to the board.
        name (Optional[str]): Board name.
        weight (Optional[int]): Weight value to be assigned to the board.
    """
    query = """
    mutation UpdateBoard($input: UpdateBoardInput!) {
      updateBoard(input: $input) {
        board {
          id
          name
          weight
          hideBacklogList
          hideClosedList
          labels {
            nodes {
              id
              title
            }
          }
          milestone {
            id
            title
          }
          assignee {
            id
            username
          }
          iteration {
            id
            title
          }
          iterationCadence {
            id
            title
          }
        }
        clientMutationId
        errors
      }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "id": id,
        }
    }
    if assignee_id is not None:
        variables["input"]["assigneeId"] = assignee_id
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id
    if hide_backlog_list is not None:
        variables["input"]["hideBacklogList"] = hide_backlog_list
    if hide_closed_list is not None:
        variables["input"]["hideClosedList"] = hide_closed_list
    if iteration_cadence_id is not None:
        variables["input"]["iterationCadenceId"] = iteration_cadence_id
    if iteration_id is not None:
        variables["input"]["iterationId"] = iteration_id
    if label_ids is not None:
        variables["input"]["labelIds"] = label_ids
    if labels is not None:
        variables["input"]["labels"] = labels
    if milestone_id is not None:
        variables["input"]["milestoneId"] = milestone_id
    if name is not None:
        variables["input"]["name"] = name
    if weight is not None:
        variables["input"]["weight"] = weight

    return _graphql_request(query, variables)

# --- Mutation.updateBoardEpicUserPreferences ---
@mcp.tool()
def update_board_epic_user_preferences(
    board_id: str,
    collapsed: bool,
    epic_id: str,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Updates user preferences for an epic on a board, such as its collapsed state.

    Args:
        board_id (str): Board global ID.
        collapsed (bool): Whether the epic should be collapsed in the board.
        epic_id (str): ID of an epic to set preferences for.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation UpdateBoardEpicUserPreferences(
      $boardId: BoardID!
      $clientMutationId: String
      $collapsed: Boolean!
      $epicId: EpicID!
    ) {
      updateBoardEpicUserPreferences(input: {
        boardId: $boardId
        clientMutationId: $clientMutationId
        collapsed: $collapsed
        epicId: $epicId
      }) {
        clientMutationId
        epicUserPreferences {
          id
          collapsed
        }
        errors
      }
    }
    """
    variables: Dict[str, Any] = {
        "boardId": board_id,
        "collapsed": collapsed,
        "epicId": epic_id,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.updateBoardList ---
@mcp.tool()
def update_board_list(
    list_id: str,
    collapsed: Optional[bool] = None,
    position: Optional[int] = None,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Updates the properties of an existing board list.

    Args:
        list_id: Global ID of the list.
        collapsed: Indicates if the list is collapsed for this user.
        position: Position of list within the board.
        client_mutation_id: A unique identifier for the client performing the mutation.
    """
    query = """
    mutation UpdateBoardList($input: UpdateBoardListInput!) {
      updateBoardList(input: $input) {
        clientMutationId
        errors
        list {
          id
          title
          listType
          position
          collapsed
        }
      }
    }
    """
    variables = {
        "input": {
            "listId": list_id,
        }
    }
    if collapsed is not None:
        variables["input"]["collapsed"] = collapsed
    if position is not None:
        variables["input"]["position"] = position
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.updateComplianceFramework ---
@mcp.tool()
def update_compliance_framework(
    framework_id: str,
    params: Dict[str, Any],
    client_mutation_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Updates an existing compliance framework.

    Args:
        framework_id (str): Global ID of the compliance framework to update.
        params (Dict[str, Any]): Parameters to update the compliance framework with, e.g., {'name': 'New Name', 'description': 'Updated description'}.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation UpdateComplianceFramework(
      $frameworkId: ComplianceManagementFrameworkID!,
      $params: ComplianceFrameworkInput!,
      $clientMutationId: String
    ) {
      updateComplianceFramework(input: {
        id: $frameworkId,
        params: $params,
        clientMutationId: $clientMutationId
      }) {
        clientMutationId
        complianceFramework {
          id
          name
          description
          color
          pipelineConfigurationFullPath
          isDefault
        }
        errors
      }
    }
    """
    variables: Dict[str, Any] = {
        "frameworkId": framework_id,
        "params": params,
        "clientMutationId": client_mutation_id,
    }
    return _graphql_request(query, variables)

# --- Mutation.updateContainerExpirationPolicy ---
from typing import Any, Dict, Optional

@mcp.tool()
def update_container_expiration_policy(
    project_path: str,
    cadence: Optional[str] = None,
    client_mutation_id: Optional[str] = None,
    enabled: Optional[bool] = None,
    keep_n: Optional[str] = None,
    name_regex: Optional[str] = None,
    name_regex_keep: Optional[str] = None,
    older_than: Optional[str] = None,
) -> Dict[str, Any]:
    """Updates the container expiration policy for a project.

    Args:
        project_path (str): Project path where the container expiration policy is located.
        cadence (Optional[str]): This container expiration policy schedule.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        enabled (Optional[bool]): Indicates whether this container expiration policy is enabled.
        keep_n (Optional[str]): Number of tags to retain.
        name_regex (Optional[str]): Tags with names matching this regex pattern will expire.
        name_regex_keep (Optional[str]): Tags with names matching this regex pattern will be preserved.
        older_than (Optional[str]): Tags older that this will expire.
    """
    query = """
    mutation UpdateContainerExpirationPolicy($input: UpdateContainerExpirationPolicyInput!) {
      updateContainerExpirationPolicy(input: $input) {
        clientMutationId
        containerExpirationPolicy {
          id
          cadence
          enabled
          keepN
          nameRegex
          nameRegexKeep
          olderThan
        }
        errors
      }
    }
    """
    input_variables: Dict[str, Any] = {
        "projectPath": project_path
    }
    if cadence is not None:
        input_variables["cadence"] = cadence
    if client_mutation_id is not None:
        input_variables["clientMutationId"] = client_mutation_id
    if enabled is not None:
        input_variables["enabled"] = enabled
    if keep_n is not None:
        input_variables["keepN"] = keep_n
    if name_regex is not None:
        input_variables["nameRegex"] = name_regex
    if name_regex_keep is not None:
        input_variables["nameRegexKeep"] = name_regex_keep
    if older_than is not None:
        input_variables["olderThan"] = older_than

    variables = {
        "input": input_variables
    }

    return _graphql_request(query, variables)

# --- Mutation.updateDependencyProxyImageTtlGroupPolicy ---
@mcp.tool()
def update_dependency_proxy_image_ttl_group_policy(
    group_path: str,
    client_mutation_id: Optional[str] = None,
    enabled: Optional[bool] = None,
    ttl: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Updates the Dependency Proxy Image TTL policy for a group.

    Args:
        group_path (str): Group path for the group dependency proxy image TTL policy.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        enabled (Optional[bool]): Indicates whether the policy is enabled or disabled.
        ttl (Optional[int]): Number of days to retain a cached image file.
    """
    query = """
    mutation UpdateDependencyProxyImageTtlGroupPolicy(
      $clientMutationId: String
      $enabled: Boolean
      $groupPath: ID!
      $ttl: Int
    ) {
      updateDependencyProxyImageTtlGroupPolicy(input: {
        clientMutationId: $clientMutationId
        enabled: $enabled
        groupPath: $groupPath
        ttl: $ttl
      }) {
        clientMutationId
        dependencyProxyImageTtlPolicy {
          id
          enabled
          ttl
          group {
            id
            fullPath
          }
        }
        errors
      }
    }
    """
    variables: Dict[str, Any] = {
        "groupPath": group_path,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id
    if enabled is not None:
        variables["enabled"] = enabled
    if ttl is not None:
        variables["ttl"] = ttl

    return _graphql_request(query, variables)

# --- Mutation.updateDependencyProxySettings ---
@mcp.tool()
def update_dependency_proxy_settings(
    group_path: str,
    enabled: Optional[bool] = None,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Updates the Dependency Proxy settings for a group.

    Args:
        group_path (str): Group path for the group dependency proxy.
        enabled (Optional[bool]): Indicates whether the policy is enabled or disabled.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation UpdateDependencyProxySettings($input: UpdateDependencyProxySettingsInput!) {
        updateDependencyProxySettings(input: $input) {
            clientMutationId
            dependencyProxySetting {
                id
                enabled
            }
            errors
        }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "groupPath": group_path,
        }
    }
    if enabled is not None:
        variables["input"]["enabled"] = enabled
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables=variables)

# --- Mutation.updateEpic ---
@mcp.tool()
def update_epic(
    group_path: str,
    iid: str,
    add_label_ids: Optional[List[str]] = None,
    add_labels: Optional[List[str]] = None,
    client_mutation_id: Optional[str] = None,
    color: Optional[str] = None,
    confidential: Optional[bool] = None,
    description: Optional[str] = None,
    due_date_fixed: Optional[str] = None,
    due_date_is_fixed: Optional[bool] = None,
    remove_label_ids: Optional[List[str]] = None,
    remove_labels: Optional[List[str]] = None,
    start_date_fixed: Optional[str] = None,
    start_date_is_fixed: Optional[bool] = None,
    state_event: Optional[str] = None,
    title: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Updates an existing GitLab epic.

    Args:
        group_path: Group the epic to mutate is in.
        iid: IID of the epic to mutate.
        add_label_ids: IDs of labels to be added to the epic.
        add_labels: Array of labels to be added to the epic.
        client_mutation_id: A unique identifier for the client performing the mutation.
        color: Color of the epic.
        confidential: Indicates if the epic is confidential.
        description: Description of the epic.
        due_date_fixed: End date of the epic.
        due_date_is_fixed: Indicates end date should be sourced from due_date_fixed field.
        remove_label_ids: IDs of labels to be removed from the epic.
        remove_labels: Array of labels to be removed from the epic.
        start_date_fixed: Start date of the epic.
        start_date_is_fixed: Indicates start date should be sourced from start_date_fixed field.
        state_event: State event for the epic.
        title: Title of the epic.
    """
    query = """
    mutation UpdateEpic($input: UpdateEpicInput!) {
      updateEpic(input: $input) {
        clientMutationId
        epic {
          id
          iid
          title
          description
          webUrl
          state
          confidential
          group {
            fullPath
          }
        }
        errors
      }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "groupPath": group_path,
            "iid": iid,
        }
    }
    if add_label_ids is not None:
        variables["input"]["addLabelIds"] = add_label_ids
    if add_labels is not None:
        variables["input"]["addLabels"] = add_labels
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id
    if color is not None:
        variables["input"]["color"] = color
    if confidential is not None:
        variables["input"]["confidential"] = confidential
    if description is not None:
        variables["input"]["description"] = description
    if due_date_fixed is not None:
        variables["input"]["dueDateFixed"] = due_date_fixed
    if due_date_is_fixed is not None:
        variables["input"]["dueDateIsFixed"] = due_date_is_fixed
    if remove_label_ids is not None:
        variables["input"]["removeLabelIds"] = remove_label_ids
    if remove_labels is not None:
        variables["input"]["removeLabels"] = remove_labels
    if start_date_fixed is not None:
        variables["input"]["startDateFixed"] = start_date_fixed
    if start_date_is_fixed is not None:
        variables["input"]["startDateIsFixed"] = start_date_is_fixed
    if state_event is not None:
        variables["input"]["stateEvent"] = state_event
    if title is not None:
        variables["input"]["title"] = title

    return _graphql_request(query, variables)

# --- Mutation.updateEpicBoardList ---
@mcp.tool()
def update_epic_board_list(
    list_id: str,
    client_mutation_id: Optional[str] = None,
    collapsed: Optional[bool] = None,
    position: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Update an existing epic board list.

    Args:
        list_id (str): Global ID of the epic list.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        collapsed (Optional[bool]): Indicates if the list is collapsed for this user.
        position (Optional[int]): Position of list within the board.
    """
    query = """
    mutation UpdateEpicBoardList(
      $clientMutationId: String
      $collapsed: Boolean
      $listId: BoardsEpicListID!
      $position: Int
    ) {
      updateEpicBoardList(input: {
        clientMutationId: $clientMutationId
        collapsed: $collapsed
        listId: $listId
        position: $position
      }) {
        clientMutationId
        errors
        list {
          id
          title
          listType
          collapsed
          position
          epicBoard {
            id
          }
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "listId": list_id,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id
    if collapsed is not None:
        variables["collapsed"] = collapsed
    if position is not None:
        variables["position"] = position

    return _graphql_request(query, variables)

# --- Mutation.updateImageDiffNote ---
@mcp.tool()
def update_image_diff_note(
    note_id: str,
    body: Optional[str] = None,
    client_mutation_id: Optional[str] = None,
    position: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Updates a DiffNote on an image.

    Args:
        note_id (str): Global ID of the note to update.
        body (Optional[str]): Content of the note.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        position (Optional[Dict[str, Any]]): Position of this note on a diff.
            Expected keys include: x, y, width, height, newPath, oldPath, positionType.
    """
    query = """
    mutation UpdateImageDiffNote(
        $id: NoteID!,
        $body: String,
        $clientMutationId: String,
        $position: UpdateDiffImagePositionInput
    ) {
        updateImageDiffNote(input: {
            id: $id,
            body: $body,
            clientMutationId: $clientMutationId,
            position: $position
        }) {
            clientMutationId
            errors
            note {
                id
                body
                createdAt
                updatedAt
                author {
                    id
                    username
                    name
                }
                position {
                    x
                    y
                    width
                    height
                    positionType
                    oldPath
                    newPath
                    diffRefs {
                        baseSha
                        headSha
                        startSha
                    }
                }
            }
        }
    }
    """
    variables = {
        "id": note_id,
        "body": body,
        "clientMutationId": client_mutation_id,
        "position": position,
    }
    return _graphql_request(query, variables)

# --- Mutation.updateIssue ---
@mcp.tool()
def update_issue(
    iid: str,
    project_path: str,
    add_label_ids: Optional[List[str]] = None,
    client_mutation_id: Optional[str] = None,
    confidential: Optional[bool] = None,
    description: Optional[str] = None,
    due_date: Optional[str] = None,
    epic_id: Optional[str] = None,
    health_status: Optional[str] = None,
    label_ids: Optional[List[str]] = None,
    locked: Optional[bool] = None,
    milestone_id: Optional[str] = None,
    remove_label_ids: Optional[List[str]] = None,
    state_event: Optional[str] = None,
    title: Optional[str] = None,
    type: Optional[str] = None,
    weight: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Updates an existing issue in a GitLab project.

    Args:
        iid: IID of the issue to mutate.
        project_path: Project the issue to mutate is in.
        add_label_ids: IDs of labels to be added to the issue.
        client_mutation_id: A unique identifier for the client performing the mutation.
        confidential: Indicates the issue is confidential.
        description: Description of the issue.
        due_date: Due date of the issue (ISO8601 format).
        epic_id: ID of the parent epic. NULL when removing the association.
        health_status: Desired health status (e.g., 'ON_TRACK', 'NEEDS_ATTENTION').
        label_ids: IDs of labels to be set. Replaces existing issue labels.
        locked: Indicates discussion is locked on the issue.
        milestone_id: ID of the milestone to assign to the issue.
        remove_label_ids: IDs of labels to be removed from the issue.
        state_event: Close or reopen an issue (e.g., 'CLOSE', 'REOPEN').
        title: Title of the issue.
        type: Type of the issue (e.g., 'INCIDENT', 'ISSUE').
        weight: Weight of the issue.
    """
    query = """
    mutation UpdateIssue($input: UpdateIssueInput!) {
      updateIssue(input: $input) {
        clientMutationId
        errors
        issue {
          id
          iid
          title
          description
          state
          confidential
          webUrl
          createdAt
          updatedAt
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "iid": iid,
            "projectPath": project_path,
        }
    }
    if add_label_ids is not None:
        variables["input"]["addLabelIds"] = add_label_ids
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id
    if confidential is not None:
        variables["input"]["confidential"] = confidential
    if description is not None:
        variables["input"]["description"] = description
    if due_date is not None:
        variables["input"]["dueDate"] = due_date
    if epic_id is not None:
        variables["input"]["epicId"] = epic_id
    if health_status is not None:
        variables["input"]["healthStatus"] = health_status
    if label_ids is not None:
        variables["input"]["labelIds"] = label_ids
    if locked is not None:
        variables["input"]["locked"] = locked
    if milestone_id is not None:
        variables["input"]["milestoneId"] = milestone_id
    if remove_label_ids is not None:
        variables["input"]["removeLabelIds"] = remove_label_ids
    if state_event is not None:
        variables["input"]["stateEvent"] = state_event
    if title is not None:
        variables["input"]["title"] = title
    if type is not None:
        variables["input"]["type"] = type
    if weight is not None:
        variables["input"]["weight"] = weight

    return _graphql_request(query, variables)

# --- Mutation.updateIteration ---
@mcp.tool()
def update_iteration(
    id: str,
    group_path: str,
    client_mutation_id: Optional[str] = None,
    description: Optional[str] = None,
    due_date: Optional[str] = None,
    start_date: Optional[str] = None,
    title: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Updates an existing iteration within a group.

    Args:
        id (str): Global ID of the iteration.
        group_path (str): Group of the iteration.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        description (Optional[str]): Description of the iteration.
        due_date (Optional[str]): End date of the iteration.
        start_date (Optional[str]): Start date of the iteration.
        title (Optional[str]): Title of the iteration.
    """
    query = """
    mutation updateIterationMutation($input: UpdateIterationInput!) {
      updateIteration(input: $input) {
        clientMutationId
        errors
        iteration {
          id
          title
          description
          startDate
          dueDate
          state
          webUrl
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "id": id,
            "groupPath": group_path,
        }
    }
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id
    if description is not None:
        variables["input"]["description"] = description
    if due_date is not None:
        variables["input"]["dueDate"] = due_date
    if start_date is not None:
        variables["input"]["startDate"] = start_date
    if title is not None:
        variables["input"]["title"] = title

    return _graphql_request(query, variables)

# --- Mutation.updateNamespacePackageSettings ---
@mcp.tool()
def update_namespace_package_settings(
    namespace_path: str,
    client_mutation_id: Optional[str] = None,
    generic_duplicate_exception_regex: Optional[str] = None,
    generic_duplicates_allowed: Optional[bool] = None,
    lock_maven_package_requests_forwarding: Optional[bool] = None,
    lock_npm_package_requests_forwarding: Optional[bool] = None,
    lock_pypi_package_requests_forwarding: Optional[bool] = None,
    maven_duplicate_exception_regex: Optional[str] = None,
    maven_duplicates_allowed: Optional[bool] = None,
    maven_package_requests_forwarding: Optional[bool] = None,
    npm_package_requests_forwarding: Optional[bool] = None,
    pypi_package_requests_forwarding: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Updates the package settings for a given namespace.

    Args:
        namespace_path (str): Namespace path where the namespace package setting is located.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        generic_duplicate_exception_regex (Optional[str]): Regex for allowed duplicate generic package names when generic_duplicates_allowed is false.
        generic_duplicates_allowed (Optional[bool]): Indicates whether duplicate generic packages are allowed.
        lock_maven_package_requests_forwarding (Optional[bool]): Indicates whether Maven package forwarding is locked for descendent namespaces.
        lock_npm_package_requests_forwarding (Optional[bool]): Indicates whether npm package forwarding is locked for descendent namespaces.
        lock_pypi_package_requests_forwarding (Optional[bool]): Indicates whether PyPI package forwarding is locked for descendent namespaces.
        maven_duplicate_exception_regex (Optional[str]): Regex for allowed duplicate Maven package names when maven_duplicates_allowed is false.
        maven_duplicates_allowed (Optional[bool]): Indicates whether duplicate Maven packages are allowed.
        maven_package_requests_forwarding (Optional[bool]): Indicates whether Maven package forwarding is allowed for this namespace.
        npm_package_requests_forwarding (Optional[bool]): Indicates whether npm package forwarding is allowed for this namespace.
        pypi_package_requests_forwarding (Optional[bool]): Indicates whether PyPI package forwarding is allowed for this namespace.
    """
    query = """
    mutation updateNamespacePackageSettings($input: UpdateNamespacePackageSettingsInput!) {
      updateNamespacePackageSettings(input: $input) {
        clientMutationId
        errors
        packageSettings {
          id
          namespace {
            id
            fullPath
          }
          genericDuplicatesAllowed
          genericDuplicateExceptionRegex
          lockMavenPackageRequestsForwarding
          lockNpmPackageRequestsForwarding
          lockPypiPackageRequestsForwarding
          mavenDuplicatesAllowed
          mavenDuplicateExceptionRegex
          mavenPackageRequestsForwarding
          npmPackageRequestsForwarding
          pypiPackageRequestsForwarding
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "namespacePath": namespace_path,
        }
    }
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id
    if generic_duplicate_exception_regex is not None:
        variables["input"]["genericDuplicateExceptionRegex"] = generic_duplicate_exception_regex
    if generic_duplicates_allowed is not None:
        variables["input"]["genericDuplicatesAllowed"] = generic_duplicates_allowed
    if lock_maven_package_requests_forwarding is not None:
        variables["input"]["lockMavenPackageRequestsForwarding"] = lock_maven_package_requests_forwarding
    if lock_npm_package_requests_forwarding is not None:
        variables["input"]["lockNpmPackageRequestsForwarding"] = lock_npm_package_requests_forwarding
    if lock_pypi_package_requests_forwarding is not None:
        variables["input"]["lockPypiPackageRequestsForwarding"] = lock_pypi_package_requests_forwarding
    if maven_duplicate_exception_regex is not None:
        variables["input"]["mavenDuplicateExceptionRegex"] = maven_duplicate_exception_regex
    if maven_duplicates_allowed is not None:
        variables["input"]["mavenDuplicatesAllowed"] = maven_duplicates_allowed
    if maven_package_requests_forwarding is not None:
        variables["input"]["mavenPackageRequestsForwarding"] = maven_package_requests_forwarding
    if npm_package_requests_forwarding is not None:
        variables["input"]["npmPackageRequestsForwarding"] = npm_package_requests_forwarding
    if pypi_package_requests_forwarding is not None:
        variables["input"]["pypiPackageRequestsForwarding"] = pypi_package_requests_forwarding

    return _graphql_request(query, variables)

# --- Mutation.updateNote ---
@mcp.tool()
def update_note(
    note_id: str,
    body: Optional[str] = None,
    client_mutation_id: Optional[str] = None,
    confidential: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Updates a Note.

    Args:
        note_id: Global ID of the note to update.
        body: Content of the note.
        client_mutation_id: A unique identifier for the client performing the mutation.
        confidential: Deprecated: No longer allowed to update confidentiality of notes.
    """
    query = """
    mutation UpdateNote(
        $note_id: NoteID!,
        $body: String,
        $client_mutation_id: String,
        $confidential: Boolean
    ) {
        updateNote(input: {
            id: $note_id,
            body: $body,
            clientMutationId: $client_mutation_id,
            confidential: $confidential
        }) {
            clientMutationId
            errors
            note {
                id
                body
                createdAt
                updatedAt
                author {
                    username
                }
                confidential
            }
        }
    }
    """
    variables: Dict[str, Any] = {
        "note_id": note_id,
    }
    if body is not None:
        variables["body"] = body
    if client_mutation_id is not None:
        variables["client_mutation_id"] = client_mutation_id
    if confidential is not None:
        variables["confidential"] = confidential

    return _graphql_request(query, variables)

# --- Mutation.updatePackagesCleanupPolicy ---
@mcp.tool()
def update_packages_cleanup_policy(
    project_path: str,
    keep_n_duplicated_package_files: Optional[str] = None,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Updates the packages cleanup policy for a project.

    Args:
        project_path (str): Project path where the packages cleanup policy is located.
        keep_n_duplicated_package_files (Optional[str]): Number of duplicated package files to retain.
                                                          (e.g., "ZERO", "ONE", "TWO", "THREE", "FIVE", "TEN", "TWENTY", "FIFTY")
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation UpdatePackagesCleanupPolicy(
      $projectPath: ID!,
      $keepNDuplicatedPackageFiles: PackagesCleanupKeepDuplicatedPackageFilesEnum,
      $clientMutationId: String
    ) {
      updatePackagesCleanupPolicy(input: {
        projectPath: $projectPath,
        keepNDuplicatedPackageFiles: $keepNDuplicatedPackageFiles,
        clientMutationId: $clientMutationId
      }) {
        clientMutationId
        errors
        packagesCleanupPolicy {
          id
          keepNDuplicatedPackageFiles
          nextRunAt
          project {
            id
            fullPath
          }
          enabled
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "projectPath": project_path,
    }
    if keep_n_duplicated_package_files is not None:
        variables["keepNDuplicatedPackageFiles"] = keep_n_duplicated_package_files
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.updateRequirement ---
@mcp.tool()
def update_requirement(
    iid: str,
    project_path: str,
    client_mutation_id: Optional[str] = None,
    description: Optional[str] = None,
    last_test_report_state: Optional[str] = None,
    state: Optional[str] = None,
    title: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Updates an existing requirement in a project.

    Args:
        iid: IID of the requirement to update.
        project_path: Full project path the requirement is associated with.
        client_mutation_id: A unique identifier for the client performing the mutation.
        description: Description of the requirement.
        last_test_report_state: Creates a test report for the requirement with the given state.
        state: State of the requirement.
        title: Title of the requirement.
    """
    query = """
    mutation UpdateRequirement($input: UpdateRequirementInput!) {
      updateRequirement(input: $input) {
        clientMutationId
        errors
        requirement {
          id
          iid
          title
          description
          state
          createdAt
          updatedAt
        }
      }
    }
    """
    variables = {
        "input": {
            "iid": iid,
            "projectPath": project_path,
        }
    }
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id
    if description is not None:
        variables["input"]["description"] = description
    if last_test_report_state is not None:
        variables["input"]["lastTestReportState"] = last_test_report_state
    if state is not None:
        variables["input"]["state"] = state
    if title is not None:
        variables["input"]["title"] = title

    return _graphql_request(query, variables)

# --- Mutation.updateSnippet ---
@mcp.tool()
def update_snippet(
    id: str,
    blob_actions: Optional[List[Dict[str, Any]]] = None,
    client_mutation_id: Optional[str] = None,
    description: Optional[str] = None,
    title: Optional[str] = None,
    visibility_level: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Updates an existing snippet in GitLab.

    Args:
        id (str): Global ID of the snippet to update.
        blob_actions (Optional[List[Dict[str, Any]]]): Actions to perform over the snippet repository and blobs.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        description (Optional[str]): Description of the snippet.
        title (Optional[str]): Title of the snippet.
        visibility_level (Optional[str]): Visibility level of the snippet (e.g., "PRIVATE", "INTERNAL", "PUBLIC").
    """
    query = """
    mutation UpdateSnippetMutation(
        $id: SnippetID!,
        $blobActions: [SnippetBlobActionInputType!],
        $clientMutationId: String,
        $description: String,
        $title: String,
        $visibilityLevel: VisibilityLevelsEnum
    ) {
        updateSnippet(input: {
            id: $id,
            blobActions: $blobActions,
            clientMutationId: $clientMutationId,
            description: $description,
            title: $title,
            visibilityLevel: $visibilityLevel
        }) {
            clientMutationId
            errors
            snippet {
                id
                title
                description
                visibilityLevel
                updatedAt
                blobs {
                    nodes {
                        path
                        size
                        rawUrl
                    }
                }
            }
        }
    }
    """
    variables: Dict[str, Any] = {
        "id": id,
        "blobActions": blob_actions,
        "clientMutationId": client_mutation_id,
        "description": description,
        "title": title,
        "visibilityLevel": visibility_level,
    }
    # Filter out None values from variables to avoid GraphQL errors for null optional inputs
    variables = {k: v for k, v in variables.items() if v is not None}

    return _graphql_request(query, variables)

# --- Mutation.uploadDelete ---
@mcp.tool()
def upload_delete(
    filename: str,
    secret: str,
    client_mutation_id: Optional[str] = None,
    group_path: Optional[str] = None,
    project_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Deletes an upload by its filename and secret.

    Args:
        filename (str): Upload filename.
        secret (str): Secret part of upload path.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        group_path (Optional[str]): Full path of the group with which the resource is associated.
        project_path (Optional[str]): Full path of the project with which the resource is associated.
    """
    query = """
    mutation UploadDelete($input: UploadDeleteInput!) {
      uploadDelete(input: $input) {
        clientMutationId
        errors
        upload {
          id
          path
          filename
          size
          contentType
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "filename": filename,
            "secret": secret,
        }
    }
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id
    if group_path is not None:
        variables["input"]["groupPath"] = group_path
    if project_path is not None:
        variables["input"]["projectPath"] = project_path

    return _graphql_request(query, variables)

# --- Mutation.userCalloutCreate ---
@mcp.tool()
def user_callout_create(feature_name: str, client_mutation_id: Optional[str] = None) -> Dict[str, Any]:
    """Dismisses a user callout for a specific feature.

    Args:
        feature_name (str): Feature name you want to dismiss the callout for.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
        mutation UserCalloutCreate($clientMutationId: String, $featureName: String!) {
          userCalloutCreate(input: { clientMutationId: $clientMutationId, featureName: $featureName }) {
            clientMutationId
            errors
            userCallout {
              id
              featureName
              dismissedAt
            }
          }
        }
    """
    variables = {
        "clientMutationId": client_mutation_id,
        "featureName": feature_name,
    }
    return _graphql_request(query, variables)

# --- Mutation.userPreferencesUpdate ---
@mcp.tool()
def user_preferences_update(
    client_mutation_id: Optional[str] = None,
    issues_sort: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Updates user preferences for sorting issues and other settings.

    Args:
        client_mutation_id: A unique identifier for the client performing the mutation.
        issues_sort: Sort order for issue lists.
    """
    query = """
    mutation UserPreferencesUpdate($clientMutationId: String, $issuesSort: IssueSort) {
      userPreferencesUpdate(input: {
        clientMutationId: $clientMutationId,
        issuesSort: $issuesSort
      }) {
        clientMutationId
        errors
        userPreferences {
          issuesSort
          timeTrackingLimit
        }
      }
    }
    """
    variables: Dict[str, Any] = {}
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id
    if issues_sort is not None:
        variables["issuesSort"] = issues_sort

    return _graphql_request(query, variables)

# --- Mutation.vulnerabilityConfirm ---
@mcp.tool()
def vulnerability_confirm(id: str, client_mutation_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Confirms the state of a vulnerability.

    Args:
        id: ID of the vulnerability to be confirmed.
        client_mutation_id: A unique identifier for the client performing the mutation.
    """
    query = """
    mutation VulnerabilityConfirm($id: VulnerabilityID!, $clientMutationId: String) {
      vulnerabilityConfirm(input: { id: $id, clientMutationId: $clientMutationId }) {
        clientMutationId
        errors
        vulnerability {
          id
          title
          state
          severity
          reportType
          vulnerabilityPath
        }
      }
    }
    """
    variables = {
        "id": id,
        "clientMutationId": client_mutation_id,
    }
    return _graphql_request(query, variables)

# --- Mutation.vulnerabilityCreate ---
@mcp.tool()
def vulnerability_create(
    description: str,
    name: str,
    project: str,
    scanner: Dict[str, Any],
    client_mutation_id: Optional[str] = None,
    confidence: Optional[str] = None,
    confirmed_at: Optional[str] = None,
    detected_at: Optional[str] = None,
    dismissed_at: Optional[str] = None,
    identifiers: Optional[List[Dict[str, Any]]] = None,
    message: Optional[str] = None,
    resolved_at: Optional[str] = None,
    severity: Optional[str] = None,
    solution: Optional[str] = None,
    state: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Creates a new vulnerability in a GitLab project.

    Args:
        description (str): Long text section that describes the vulnerability in more detail.
        name (str): Name of the vulnerability.
        project (str): ID of the project to attach the vulnerability to (e.g., "gid://gitlab/Project/123").
        scanner (Dict[str, Any]): Information about the scanner used to discover the vulnerability.
                                   Example: `{"id": "gid://gitlab/VulnerabilityScanner/1", "name": "Security Scanner"}`.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        confidence (Optional[str]): Deprecated. Confidence of the vulnerability (e.g., "HIGH", "MEDIUM"). Will be removed in 15.4.
        confirmed_at (Optional[str]): Timestamp of when the vulnerability state changed to confirmed (ISO 8601 format).
        detected_at (Optional[str]): Timestamp of when the vulnerability was first detected (ISO 8601 format).
        dismissed_at (Optional[str]): Timestamp of when the vulnerability state changed to dismissed (ISO 8601 format).
        identifiers (Optional[List[Dict[str, Any]]]): Array of CVE or CWE identifiers.
                                                      Example: `[{"type": "CVE", "value": "CVE-2023-1234"}]`.
        message (Optional[str]): Short text section that describes the vulnerability.
        resolved_at (Optional[str]): Timestamp of when the vulnerability state changed to resolved (ISO 8601 format).
        severity (Optional[str]): Severity of the vulnerability (e.g., "CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO", "UNKNOWN").
        solution (Optional[str]): Instructions for how to fix the vulnerability.
        state (Optional[str]): State of the vulnerability (e.g., "DETECTED", "CONFIRMED", "DISMISSED", "RESOLVED").
    """
    query = """
    mutation vulnerabilityCreate($input: VulnerabilityCreateInput!) {
        vulnerabilityCreate(input: $input) {
            clientMutationId
            errors
            vulnerability {
                id
                name
                description
                severity
                state
            }
        }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "description": description,
            "name": name,
            "project": project,
            "scanner": scanner,
        }
    }

    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id
    if confidence is not None:
        variables["input"]["confidence"] = confidence
    if confirmed_at is not None:
        variables["input"]["confirmedAt"] = confirmed_at
    if detected_at is not None:
        variables["input"]["detectedAt"] = detected_at
    if dismissed_at is not None:
        variables["input"]["dismissedAt"] = dismissed_at
    if identifiers is not None:
        variables["input"]["identifiers"] = identifiers
    if message is not None:
        variables["input"]["message"] = message
    if resolved_at is not None:
        variables["input"]["resolvedAt"] = resolved_at
    if severity is not None:
        variables["input"]["severity"] = severity
    if solution is not None:
        variables["input"]["solution"] = solution
    if state is not None:
        variables["input"]["state"] = state

    return _graphql_request(query, variables=variables)

# --- Mutation.vulnerabilityDismiss ---
@mcp.tool()
def vulnerability_dismiss(
    id: str,
    comment: Optional[str] = None,
    dismissal_reason: Optional[str] = None,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Dismisses a vulnerability.

    Args:
        id: ID of the vulnerability to be dismissed.
        comment: Comment why vulnerability should be dismissed (max. 50 000 characters).
        dismissal_reason: Reason why vulnerability should be dismissed.
        client_mutation_id: A unique identifier for the client performing the mutation.
    """
    variables = {
        "id": id,
    }
    input_fields = ["id: $id"]

    if comment is not None:
        variables["comment"] = comment
        input_fields.append("comment: $comment")
    if dismissal_reason is not None:
        variables["dismissalReason"] = dismissal_reason
        input_fields.append("dismissalReason: $dismissalReason")
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id
        input_fields.append("clientMutationId: $clientMutationId")

    # Define GraphQL variable types for the query
    graphql_variables = []
    if client_mutation_id is not None:
        graphql_variables.append("$clientMutationId: String")
    if comment is not None:
        graphql_variables.append("$comment: String")
    if dismissal_reason is not None:
        graphql_variables.append("$dismissalReason: VulnerabilityDismissalReason")
    graphql_variables.append("$id: VulnerabilityID!") # Required

    query_variables_str = f"({', '.join(graphql_variables)})" if graphql_variables else ""
    input_str = ", ".join(input_fields)

    query = f"""
    mutation VulnerabilityDismiss{query_variables_str} {{
      vulnerabilityDismiss(input: {{ {input_str} }}) {{
        clientMutationId
        errors
        vulnerability {{
          id
          title
          state
          severity
          confidence
          reportType
          dismissalReason
          resolvedOnFullBranch
        }}
      }}
    }}
    """
    return _graphql_request(query, variables)

# --- Mutation.vulnerabilityExternalIssueLinkCreate ---
@mcp.tool()
def vulnerability_external_issue_link_create(
    external_tracker: str,
    vulnerability_id: str,
    link_type: str,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Creates an external issue link for a vulnerability.

    Args:
        external_tracker (str): External tracker type of the external issue link.
        vulnerability_id (str): ID of the vulnerability.
        link_type (str): Type of the external issue link.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation VulnerabilityExternalIssueLinkCreate(
      $input: VulnerabilityExternalIssueLinkCreateInput!
    ) {
      vulnerabilityExternalIssueLinkCreate(input: $input) {
        clientMutationId
        errors
        externalIssueLink {
          id
          linkType
          externalTracker
          externalId
          issueUrl
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "externalTracker": external_tracker,
            "id": vulnerability_id,
            "linkType": link_type,
        }
    }
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.vulnerabilityExternalIssueLinkDestroy ---
@mcp.tool()
def vulnerability_external_issue_link_destroy(
    id: str,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Destroys a vulnerability external issue link.

    Args:
        id (str): Global ID of the vulnerability external issue link.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation VulnerabilityExternalIssueLinkDestroy($input: VulnerabilityExternalIssueLinkDestroyInput!) {
      vulnerabilityExternalIssueLinkDestroy(input: $input) {
        clientMutationId
        errors
      }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "id": id,
        }
    }
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.vulnerabilityFindingDismiss ---
@mcp.tool()
def vulnerability_finding_dismiss(
    client_mutation_id: Optional[str] = None,
    comment: Optional[str] = None,
    dismissal_reason: Optional[str] = None,
    id: Optional[str] = None,
    uuid: Optional[str] = None,
) -> Dict[str, Any]:
    """Dismisses a security finding.

    Args:
        client_mutation_id: A unique identifier for the client performing the mutation.
        comment: Comment why finding should be dismissed.
        dismissal_reason: Reason why finding should be dismissed (e.g., "FALSE_POSITIVE", "RISK_ACCEPTED").
        id: **Deprecated:** Use `uuid`. ID of the finding to be dismissed.
        uuid: UUID of the finding to be dismissed. One of `id` or `uuid` should typically be provided.
    """
    query = """
    mutation VulnerabilityFindingDismiss($input: VulnerabilityFindingDismissInput!) {
      vulnerabilityFindingDismiss(input: $input) {
        clientMutationId
        errors
        finding {
          id
          uuid
          name
          description
          severity
          state
          dismissalReason
          scanner {
            id
            name
          }
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "input": {}
    }
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id
    if comment is not None:
        variables["input"]["comment"] = comment
    if dismissal_reason is not None:
        variables["input"]["dismissalReason"] = dismissal_reason
    if id is not None:
        variables["input"]["id"] = id
    if uuid is not None:
        variables["input"]["uuid"] = uuid

    return _graphql_request(query, variables)

# --- Mutation.vulnerabilityResolve ---
@mcp.tool()
def vulnerability_resolve(
    vulnerability_id: str,
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Resolves a GitLab vulnerability.

    Args:
        vulnerability_id: ID of the vulnerability to be resolved.
        client_mutation_id: A unique identifier for the client performing the mutation.
    """
    query = """
        mutation VulnerabilityResolveMutation($id: VulnerabilityID!, $clientMutationId: String) {
            vulnerabilityResolve(input: { id: $id, clientMutationId: $clientMutationId }) {
                clientMutationId
                errors
                vulnerability {
                    id
                    title
                    state
                    severity
                    reportType
                    description
                    externalId
                    project {
                        id
                        name
                        fullPath
                    }
                    scanner {
                        id
                        name
                    }
                }
            }
        }
    """
    variables: Dict[str, Any] = {
        "id": vulnerability_id,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.vulnerabilityRevertToDetected ---
@mcp.tool()
def vulnerability_revert_to_detected(id: str, client_mutation_id: Optional[str] = None) -> Dict[str, Any]:
    """Reverts a vulnerability to the 'detected' state.

    Args:
        id (str): ID of the vulnerability to be reverted.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation vulnerabilityRevertToDetected($id: VulnerabilityID!, $clientMutationId: String) {
      vulnerabilityRevertToDetected(input: { id: $id, clientMutationId: $clientMutationId }) {
        clientMutationId
        errors
        vulnerability {
          id
          state
          severity
          reportType
          title
        }
      }
    }
    """
    variables = {
        "id": id,
        "clientMutationId": client_mutation_id,
    }
    return _graphql_request(query, variables)

# --- Mutation.workItemCreate ---
@mcp.tool()
def work_item_create(
    project_path: str,
    title: str,
    work_item_type_id: str,
    client_mutation_id: Optional[str] = None,
    confidential: Optional[bool] = None,
    description: Optional[str] = None,
    hierarchy_widget: Optional[Dict[str, Any]] = None,
    iteration_widget: Optional[Dict[str, Any]] = None,
    milestone_widget: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Creates a new work item in a GitLab project.

    Args:
        project_path (str): Full path of the project the work item is associated with.
        title (str): Title of the work item.
        work_item_type_id (str): Global ID of a work item type.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        confidential (Optional[bool]): Sets the work item confidentiality.
        description (Optional[str]): Description of the work item.
        hierarchy_widget (Optional[Dict[str, Any]]): Input for hierarchy widget.
        iteration_widget (Optional[Dict[str, Any]]): Iteration widget of the work item.
        milestone_widget (Optional[Dict[str, Any]]): Input for milestone widget.
    """
    query = """
    mutation WorkItemCreateMutation(
      $projectPath: ID!,
      $title: String!,
      $workItemTypeId: WorkItemsTypeID!,
      $clientMutationId: String,
      $confidential: Boolean,
      $description: String,
      $hierarchyWidget: WorkItemWidgetHierarchyCreateInput,
      $iterationWidget: WorkItemWidgetIterationInput,
      $milestoneWidget: WorkItemWidgetMilestoneInput
    ) {
      workItemCreate(input: {
        projectPath: $projectPath,
        title: $title,
        workItemTypeId: $workItemTypeId,
        clientMutationId: $clientMutationId,
        confidential: $confidential,
        description: $description,
        hierarchyWidget: $hierarchyWidget,
        iterationWidget: $iterationWidget,
        milestoneWidget: $milestoneWidget
      }) {
        clientMutationId
        errors
        workItem {
          id
          title
          description
          confidential
          state
          webUrl
          workItemType {
            name
            id
          }
          createdAt
          updatedAt
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "projectPath": project_path,
        "title": title,
        "workItemTypeId": work_item_type_id,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id
    if confidential is not None:
        variables["confidential"] = confidential
    if description is not None:
        variables["description"] = description
    if hierarchy_widget is not None:
        variables["hierarchyWidget"] = hierarchy_widget
    if iteration_widget is not None:
        variables["iterationWidget"] = iteration_widget
    if milestone_widget is not None:
        variables["milestoneWidget"] = milestone_widget

    return _graphql_request(query, variables)

# --- Mutation.workItemCreateFromTask ---
@mcp.tool()
def work_item_create_from_task(
    id: str,
    work_item_data: Dict[str, Any],
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Creates a work item from a task in another work item's description.

    Args:
        id (str): Global ID of the work item.
        work_item_data (Dict[str, Any]): Arguments necessary to convert a task into a work item.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation WorkItemCreateFromTask($id: WorkItemID!, $workItemData: WorkItemConvertTaskInput!, $clientMutationId: String) {
      workItemCreateFromTask(input: {
        id: $id,
        workItemData: $workItemData,
        clientMutationId: $clientMutationId
      }) {
        clientMutationId
        errors
        newWorkItem {
          id
          title
          iid
          webUrl
          workItemType {
            name
          }
        }
        workItem {
          id
          title
          iid
          webUrl
          workItemType {
            name
          }
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "id": id,
        "workItemData": work_item_data,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables=variables)

# --- Mutation.workItemDelete ---
@mcp.tool()
def work_item_delete(id: str, client_mutation_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Deletes a work item.

    Args:
        id: Global ID of the work item to delete.
        client_mutation_id: A unique identifier for the client performing the mutation.
    """
    query = """
    mutation WorkItemDelete($id: WorkItemID!, $clientMutationId: String) {
      workItemDelete(input: { id: $id, clientMutationId: $clientMutationId }) {
        clientMutationId
        errors
        project {
          id
          fullPath
          name
          webUrl
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "id": id,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.workItemDeleteTask ---
@mcp.tool()
def work_item_delete_task(
    id: str,
    lock_version: int,
    task_data: Dict[str, Any],
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Deletes a task in a work item's description.

    Args:
        id (str): Global ID of the work item.
        lock_version (int): Current lock version of the work item containing the task in the description.
        task_data (Dict[str, Any]): Arguments necessary to delete a task from a work item's description.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation WorkItemDeleteTask(
      $clientMutationId: String,
      $id: WorkItemID!,
      $lockVersion: Int!,
      $taskData: WorkItemDeletedTaskInput!
    ) {
      workItemDeleteTask(input: {
        clientMutationId: $clientMutationId,
        id: $id,
        lockVersion: $lockVersion,
        taskData: $taskData
      }) {
        clientMutationId
        errors
        workItem {
          id
          title
          description
          lockVersion
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "id": id,
        "lockVersion": lock_version,
        "taskData": task_data,
    }
    if client_mutation_id is not None:
        variables["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)

# --- Mutation.workItemUpdate ---
@mcp.tool()
def work_item_update(
    id: str,
    assignees_widget: Optional[Dict[str, Any]] = None,
    client_mutation_id: Optional[str] = None,
    confidential: Optional[bool] = None,
    description_widget: Optional[Dict[str, Any]] = None,
    health_status_widget: Optional[Dict[str, Any]] = None,
    hierarchy_widget: Optional[Dict[str, Any]] = None,
    iteration_widget: Optional[Dict[str, Any]] = None,
    labels_widget: Optional[Dict[str, Any]] = None,
    milestone_widget: Optional[Dict[str, Any]] = None,
    progress_widget: Optional[Dict[str, Any]] = None,
    start_and_due_date_widget: Optional[Dict[str, Any]] = None,
    state_event: Optional[str] = None,
    status_widget: Optional[Dict[str, Any]] = None,
    title: Optional[str] = None,
    weight_widget: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Updates a work item by Global ID.

    Args:
        id (str): Global ID of the work item.
        assignees_widget (Optional[Dict[str, Any]]): Input for assignees widget.
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
        confidential (Optional[bool]): Sets the work item confidentiality.
        description_widget (Optional[Dict[str, Any]]): Input for description widget.
        health_status_widget (Optional[Dict[str, Any]]): Input for health status widget.
        hierarchy_widget (Optional[Dict[str, Any]]): Input for hierarchy widget.
        iteration_widget (Optional[Dict[str, Any]]): Input for iteration widget.
        labels_widget (Optional[Dict[str, Any]]): Input for labels widget.
        milestone_widget (Optional[Dict[str, Any]]): Input for milestone widget.
        progress_widget (Optional[Dict[str, Any]]): Input for progress widget.
        start_and_due_date_widget (Optional[Dict[str, Any]]): Input for start and due date widget.
        state_event (Optional[str]): Close or reopen a work item.
        status_widget (Optional[Dict[str, Any]]): Input for status widget.
        title (Optional[str]): Title of the work item.
        weight_widget (Optional[Dict[str, Any]]): Input for weight widget.
    """
    query_vars: Dict[str, Any] = {}
    graphql_var_types = {
        "id": "WorkItemID!",
        "assigneesWidget": "WorkItemWidgetAssigneesInput",
        "clientMutationId": "String",
        "confidential": "Boolean",
        "descriptionWidget": "WorkItemWidgetDescriptionInput",
        "healthStatusWidget": "WorkItemWidgetHealthStatusInput",
        "hierarchyWidget": "WorkItemWidgetHierarchyUpdateInput",
        "iterationWidget": "WorkItemWidgetIterationInput",
        "labelsWidget": "WorkItemWidgetLabelsUpdateInput",
        "milestoneWidget": "WorkItemWidgetMilestoneInput",
        "progressWidget": "WorkItemWidgetProgressInput",
        "startAndDueDateWidget": "WorkItemWidgetStartAndDueDateUpdateInput",
        "stateEvent": "WorkItemStateEvent",
        "statusWidget": "StatusInput",
        "title": "String",
        "weightWidget": "WorkItemWidgetWeightInput",
    }

    # Add required 'id'
    query_vars["id"] = id

    # Conditionally add optional arguments
    if assignees_widget is not None:
        query_vars["assigneesWidget"] = assignees_widget
    if client_mutation_id is not None:
        query_vars["clientMutationId"] = client_mutation_id
    if confidential is not None:
        query_vars["confidential"] = confidential
    if description_widget is not None:
        query_vars["descriptionWidget"] = description_widget
    if health_status_widget is not None:
        query_vars["healthStatusWidget"] = health_status_widget
    if hierarchy_widget is not None:
        query_vars["hierarchyWidget"] = hierarchy_widget
    if iteration_widget is not None:
        query_vars["iterationWidget"] = iteration_widget
    if labels_widget is not None:
        query_vars["labelsWidget"] = labels_widget
    if milestone_widget is not None:
        query_vars["milestoneWidget"] = milestone_widget
    if progress_widget is not None:
        query_vars["progressWidget"] = progress_widget
    if start_and_due_date_widget is not None:
        query_vars["startAndDueDateWidget"] = start_and_due_date_widget
    if state_event is not None:
        query_vars["stateEvent"] = state_event
    if status_widget is not None:
        query_vars["statusWidget"] = status_widget
    if title is not None:
        query_vars["title"] = title
    if weight_widget is not None:
        query_vars["weightWidget"] = weight_widget

    # Build variable definitions and mutation arguments from populated query_vars
    var_definitions = []
    mutation_args_list = []
    for var_name, _ in query_vars.items():
        var_definitions.append(f"${var_name}: {graphql_var_types[var_name]}")
        mutation_args_list.append(f"{var_name}: ${var_name}")

    var_definitions_str = ", ".join(var_definitions)
    mutation_args_str = ", ".join(mutation_args_list)

    query = f"""
    mutation WorkItemUpdate({var_definitions_str}) {{
        workItemUpdate(input: {{ {mutation_args_str} }}) {{
            clientMutationId
            errors
            workItem {{
                id
                title
                state
                confidential
            }}
        }}
    }}
    """
    return _graphql_request(query, query_vars)

# --- Mutation.workItemUpdateTask ---
@mcp.tool()
def work_item_update_task(
    id: str,
    task_data: Dict[str, Any],
    client_mutation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Updates a work item's task by Global ID.

    Args:
        id (str): Global ID of the work item.
        task_data (Dict[str, Any]): Arguments necessary to update a task (e.g., {'checked': True, 'text': 'Updated text'}).
        client_mutation_id (Optional[str]): A unique identifier for the client performing the mutation.
    """
    query = """
    mutation WorkItemUpdateTask($input: WorkItemUpdateTaskInput!) {
      workItemUpdateTask(input: $input) {
        clientMutationId
        errors
        task {
          id
          title
          state
          checked
          description
        }
        workItem {
          id
          title
          state
          description
        }
      }
    }
    """
    variables: Dict[str, Any] = {
        "input": {
            "id": id,
            "taskData": task_data,
        }
    }
    if client_mutation_id is not None:
        variables["input"]["clientMutationId"] = client_mutation_id

    return _graphql_request(query, variables)


if __name__ == "__main__":
    # Run GitLab MCP server over HTTP (streamable-http transport) so the agent can connect via URL.
    #
    # IMPORTANT:
    # - This server URL (below) is NOT your GitLab instance URL.
    # - Your GitLab instance is at GITLAB_BASE_URL (default http://127.0.0.1:8023).
    # - The MCP server must listen on a DIFFERENT port than GitLab to avoid conflicts.
    from agent.common.configurator import Configurator
    from agent.common.utils import get_mcp_logger

    logger = get_mcp_logger()
    logger.debug("Starting gitlab-mcp server (streamable-http)")

    config = Configurator()
    config.load_mcpserver_env()
    config.load_shared_env()

    # Re-read the token now that .server_env has been loaded into the environment
    auth["token"] = os.getenv("GRAPHQL_TOKEN", auth.get("token"))

    # Read URL from config.yaml -> mcp_server.gitlab
    # Example: http://localhost:8001/
    mcp_server_url = config.get_key("mcp_server")["gitlab"]
    hostname, port, path = config.get_hostname_port(mcp_server_url)

    mcp.run(
        transport="streamable-http",
        host=hostname,
        port=port,
        path=path,
    )