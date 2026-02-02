"""GitLab project management helpers."""

from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

from playwright.sync_api import Page, TimeoutError

from .constants import (
    GITLAB_DOMAIN,
    NEW_PROJECT_URL,
    DASHBOARD_PROJECTS_URL,
    Selectors,
    get_project_settings_url,
)


@dataclass
class Project:
    """Representation of a GitLab project."""

    name: str
    slug: str
    namespace: str
    url: str
    visibility: Optional[str] = None  # "private", "internal", "public"


@dataclass
class CreateProjectResult:
    """Result of attempting to create a project."""

    success: bool
    project_slug: Optional[str]
    project_url: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class DeleteProjectResult:
    """Result of attempting to delete a project."""

    success: bool
    error_message: Optional[str] = None


def create_private_project(
    page: Page,
    project_name: str,
    namespace_name: Optional[str] = None,
    timeout_for_dropdown: int = 5000,
) -> CreateProjectResult:
    """
    Create a new private project in GitLab.

    FIXED: Uses sync pattern instead of expect_navigation context manager.

    Args:
        page: Playwright Page instance
        project_name: Name for the new project
        namespace_name: Optional namespace (group/user) to create under.
                       If not provided, uses the default prefilled namespace.
        timeout_for_dropdown: Timeout in ms for namespace dropdown to load

    Returns:
        CreateProjectResult with success status, slug, and any error message
    """
    page.goto(NEW_PROJECT_URL, wait_until="networkidle")

    # Fill project name
    name_locator = page.get_by_label("Project name")
    try:
        name_locator.wait_for(state="visible", timeout=10000)
    except TimeoutError:
        return CreateProjectResult(
            success=False,
            project_slug=None,
            error_message="Project name field not found"
        )

    name_locator.fill(project_name)

    # Wait for JS-driven URL slug generation
    page.wait_for_timeout(2000)

    # Handle namespace selection if specified
    if namespace_name:
        result = _select_namespace(page, namespace_name, timeout_for_dropdown)
        if result:  # result is an error message
            return CreateProjectResult(
                success=False,
                project_slug=None,
                error_message=result
            )

    # Select private visibility
    try:
        page.locator("#blank-project-pane").get_by_text(
            "PrivateProject access must be"
        ).check()
    except Exception:
        # Try alternative selector
        try:
            page.locator("label[for='project_visibility_level_0']").check()
        except Exception:
            pass  # Continue anyway, may have different visibility options

    # Submit - FIXED: sync pattern
    page.get_by_role("button", name="Create project").click()
    page.wait_for_load_state("networkidle")

    # Check if we got a URL collision error
    if page.url.endswith("projects"):
        return _handle_project_creation_error(page, project_name, namespace_name)

    # Check for error messages
    error_container = page.locator(Selectors.PROJECT_ERROR_CONTAINER)
    if error_container.count() > 0:
        errors = error_container.locator("ul li").all_inner_texts()
        error_message = "; ".join(errors)

        # Check if project already exists
        if "taken" in error_message.lower():
            return CreateProjectResult(
                success=True,
                project_slug=project_name,
                project_url=None,
                error_message=f"Project may already exist: {error_message}"
            )

        return CreateProjectResult(
            success=False,
            project_slug=None,
            error_message=error_message
        )

    # Extract project slug from final URL
    final_url = page.url
    parsed = urlparse(final_url)
    project_slug = parsed.path.strip("/").split("/")[-1]

    return CreateProjectResult(
        success=True,
        project_slug=project_slug,
        project_url=final_url,
        error_message=None
    )


def delete_project(
    page: Page,
    namespace: str,
    project: str,
) -> DeleteProjectResult:
    """
    Delete a project from GitLab.

    FIXED: Uses sync pattern instead of expect_navigation context manager.

    Args:
        page: Playwright Page instance
        namespace: Project namespace
        project: Project name

    Returns:
        DeleteProjectResult with success status and any error message
    """
    settings_url = get_project_settings_url(namespace, project)
    confirmation_phrase = f"{namespace}/{project}"

    return _delete_project_or_group(
        page=page,
        url=settings_url,
        confirmation_phrase=confirmation_phrase,
        delete_section_id=Selectors.DELETE_PROJECT_SECTION.lstrip("#"),
        trigger_button_text="Delete project",
        confirm_button_text="Yes, delete project",
        success_url=DASHBOARD_PROJECTS_URL,
    )


def _select_namespace(
    page: Page,
    namespace_name: str,
    timeout: int,
) -> Optional[str]:
    """
    Select a namespace from the dropdown if available.

    Returns None on success, error message on failure.
    """
    dropdown_button = page.locator(Selectors.NAMESPACE_DROPDOWN_BUTTON)

    if dropdown_button.is_visible():
        # Multiple namespaces available
        dropdown_button.click()
        page.wait_for_timeout(timeout)

        group_item = page.locator(
            f"li.gl-dropdown-item >> text={namespace_name}"
        )

        if not group_item.is_visible():
            return f"Namespace '{namespace_name}' not found in dropdown"

        group_item.click()
        return None

    # Single namespace - check if it matches
    prefilled_element = page.query_selector(".input-group-prepend.static-namespace")
    if prefilled_element:
        prefilled_url = prefilled_element.get_attribute("title") or ""
        parsed = urlparse(prefilled_url)
        prefilled_namespace = parsed.path.strip("/").split("/")[-1]

        if prefilled_namespace != namespace_name:
            return (
                f"Namespace '{namespace_name}' requested but page shows "
                f"'{prefilled_namespace}'. Create the namespace first."
            )

    return None


def _handle_project_creation_error(
    page: Page,
    project_name: str,
    namespace_name: Optional[str],
) -> CreateProjectResult:
    """Handle errors during project creation."""
    error_container = page.locator(Selectors.PROJECT_ERROR_CONTAINER)
    if error_container.count() > 0:
        errors = error_container.locator("ul li").all_inner_texts()
        error_message = "; ".join(errors)

        if "taken" in error_message.lower():
            return CreateProjectResult(
                success=True,
                project_slug=project_name,
                error_message=f"Project may already exist: {error_message}"
            )

        return CreateProjectResult(
            success=False,
            project_slug=None,
            error_message=error_message
        )

    return CreateProjectResult(
        success=False,
        project_slug=None,
        error_message=f"Failed to create project; ended up at {page.url}"
    )


def _delete_project_or_group(
    page: Page,
    url: str,
    confirmation_phrase: str,
    delete_section_id: str,
    trigger_button_text: str,
    confirm_button_text: str,
    success_url: str,
) -> DeleteProjectResult:
    """
    Shared deletion logic for projects and groups.

    FIXED: Uses sync pattern instead of expect_navigation context manager.
    """
    page.goto(url, wait_until="networkidle")

    # Check for page not found
    if _is_page_not_found(page):
        # Already deleted
        return DeleteProjectResult(success=True)

    # Expand the advanced settings section
    try:
        expand_selector = f"section#{delete_section_id} {Selectors.EXPAND_BUTTON}"
        page.click(expand_selector)
    except Exception:
        return DeleteProjectResult(
            success=False,
            error_message="Could not expand settings section"
        )

    # Click delete trigger button
    delete_button = f'button:has-text("{trigger_button_text}")'
    try:
        page.wait_for_selector(delete_button, timeout=3000)
        page.locator(delete_button).click()
    except TimeoutError:
        return DeleteProjectResult(
            success=False,
            error_message=f"Delete button '{trigger_button_text}' not found"
        )

    # Fill confirmation input
    try:
        page.wait_for_selector(Selectors.CONFIRM_NAME_INPUT, timeout=3000)
        page.locator(Selectors.CONFIRM_NAME_INPUT).fill(confirmation_phrase)
    except TimeoutError:
        return DeleteProjectResult(
            success=False,
            error_message="Confirmation input not found"
        )

    # Confirm deletion - FIXED: sync pattern
    confirm_button = f'button:has-text("{confirm_button_text}")'
    page.locator(confirm_button).click()
    page.wait_for_load_state("networkidle")

    # Verify deletion
    if page.url == success_url:
        alert = page.locator(Selectors.ALERT_BODY)
        if alert.count() > 0:
            text = alert.text_content() or ""
            if "being deleted" in text or "deleted" in text.lower():
                return DeleteProjectResult(success=True)

    # Check if we're on a different success page
    if "/dashboard" in page.url or page.url.rstrip("/") == GITLAB_DOMAIN.rstrip("/"):
        return DeleteProjectResult(success=True)

    return DeleteProjectResult(
        success=False,
        error_message=f"Deletion may have failed; ended up at {page.url}"
    )


def _is_page_not_found(page: Page) -> bool:
    """Check if the current page shows a 'Page Not Found' error."""
    container = page.locator(Selectors.PAGE_NOT_FOUND)
    if container.count() > 0:
        text = container.text_content()
        if text and "Page Not Found" in text:
            return True
    return False
