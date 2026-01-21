"""
Unified Postmill (Reddit-like) API
Combines authentication, browsing, searching, and posting functionality

Note: Uses SYNC Playwright for reliability (async had event loop conflicts)
"""

from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field, EmailStr
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page
from fastmcp import FastMCP

# Initialize MCP server
mcp = FastMCP("Postmill Reddit API")

# Module-level browser state
_browser: Browser = None
_context: BrowserContext = None
_page: Page = None
_playwright = None

BASE_URL = "http://ec2-18-218-205-96.us-east-2.compute.amazonaws.com:8080/"

browser_state = {
    "is_logged_in": False,
    "username": None
}


# ============================================================================
# BROWSER MANAGEMENT
# ============================================================================

def get_page() -> Page:
    """Get or create browser page (SYNC)"""
    global _browser, _context, _page, _playwright
    
    if _page is None or _browser is None:
        if _playwright is None:
            _playwright = sync_playwright().start()
        
        if _browser is None:
            _browser = _playwright.chromium.launch(
                headless=True,
                args=['--disable-blink-features=AutomationControlled']
            )
        
        _context = _browser.new_context(
            bypass_csp=True,
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        )
        _page = _context.new_page()
    
    return _page


@mcp.tool()
def cleanup_browser() -> Dict[str, Any]:
    """Close browser and clean up resources"""
    global _browser, _context, _page, _playwright
    
    if _page:
        _page.close()
        _page = None
    
    if _context:
        _context.close()
        _context = None
    
    if _browser:
        _browser.close()
        _browser = None
    
    if _playwright:
        _playwright.stop()
        _playwright = None
    
    return {"success": True, "message": "Browser cleaned up"}


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class RegistrationData(BaseModel):
    """User registration data"""
    username: str = Field(description="Desired username")
    email: EmailStr = Field(description="Valid email address")
    password: str = Field(description="Password (minimum 8 characters)")


class LoginData(BaseModel):
    """User login data"""
    username: str = Field(description="Username or email")
    password: str = Field(description="User password")
    remember_me: bool = Field(default=True, description="Keep user logged in")


class SubmissionData(BaseModel):
    """Data for creating a submission"""
    forum: str = Field(description="Forum name (without f/ prefix)")
    title: str = Field(description="Submission title")
    body: Optional[str] = Field(default="", description="Post body (optional for links)")
    url: Optional[str] = Field(default=None, description="URL for link posts")


class CommentData(BaseModel):
    """Data for creating a comment"""
    body: str = Field(description="Comment text")


class SearchOptions(BaseModel):
    """Advanced search options"""
    query: str = Field(description="Search query")
    forum: Optional[str] = Field(default=None, description="Limit to specific forum")
    author: Optional[str] = Field(default=None, description="Filter by author")
    sort: str = Field(default="relevance", description="Sort: relevance, new, top")
    time: Optional[str] = Field(default=None, description="Time: hour, day, week, month, year, all")
    type: str = Field(default="submissions", description="Type: submissions or comments")
    page: int = Field(default=1, description="Page number")


# ============================================================================
# AUTHENTICATION
# ============================================================================

@mcp.tool()
def register_user(data: RegistrationData) -> Dict[str, Any]:
    """
    Register a new user account
    
    Example:
        register_user(RegistrationData(
            username="john_doe",
            email="john@example.com",
            password="SecurePass123!"
        ))
    """
    try:
        page = get_page()
        
        page.goto(f"{BASE_URL}registration", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(500)
        
        # Fill form with correct field names
        page.fill('input[name="user[username]"]', data.username)
        page.fill('input[name="user[email]"]', data.email)
        page.fill('input[name="user[password][first]"]', data.password)
        page.fill('input[name="user[password][second]"]', data.password)
        
        # Submit
        page.click('button:has-text("Sign up")')
        page.wait_for_load_state("domcontentloaded", timeout=30000)
        
        # Check result
        if page.locator('.alert-danger, .error').count() > 0:
            error_text = page.locator('.alert-danger, .error').first.text_content()
            return {"success": False, "error": error_text.strip()}
        
        if "registration" in page.url.lower():
            return {"success": False, "error": "Registration failed"}
        
        return {
            "success": True,
            "message": "Registration successful",
            "username": data.username
        }
    
    except Exception as e:
        return {"success": False, "error": f"Registration error: {str(e)}"}


@mcp.tool()
def login(data: LoginData) -> Dict[str, Any]:
    """
    Log in a user
    
    Example:
        login(LoginData(
            username="john_doe",
            password="SecurePass123!",
            remember_me=True
        ))
    """
    try:
        page = get_page()
        
        page.goto(f"{BASE_URL}login", wait_until="domcontentloaded", timeout=30000)
        
        page.fill('input[name="_username"]', data.username)
        page.fill('input[name="_password"]', data.password)
        
        if data.remember_me:
            page.check('input[name="_remember_me"]')
        
        page.click('button:has-text("Log in")')
        page.wait_for_load_state("domcontentloaded", timeout=30000)
        
        if "login" in page.url.lower():
            if page.locator('.alert-danger, .error').count() > 0:
                error_text = page.locator('.alert-danger, .error').first.text_content()
                return {"success": False, "error": error_text.strip()}
            return {"success": False, "error": "Invalid credentials"}
        
        browser_state["is_logged_in"] = True
        browser_state["username"] = data.username
        
        return {
            "success": True,
            "message": "Login successful",
            "username": data.username
        }
    
    except Exception as e:
        return {"success": False, "error": f"Login error: {str(e)}"}


@mcp.tool()
def logout() -> Dict[str, Any]:
    """Log out the current user"""
    try:
        if not browser_state.get("is_logged_in"):
            return {"success": False, "error": "Not logged in"}
        
        page = get_page()
        
        logout_elem = page.locator('a[href*="logout"]')
        if logout_elem.count() > 0:
            logout_elem.first.click()
            page.wait_for_load_state("domcontentloaded")
            
            browser_state["is_logged_in"] = False
            browser_state["username"] = None
            
            return {"success": True, "message": "Logged out successfully"}
        
        return {"success": False, "error": "Logout button not found"}
    
    except Exception as e:
        return {"success": False, "error": f"Logout error: {str(e)}"}


@mcp.tool()
def check_login_status() -> Dict[str, Any]:
    """Check if a user is currently logged in"""
    return {
        "is_logged_in": browser_state.get("is_logged_in", False),
        "username": browser_state.get("username")
    }


# ============================================================================
# BROWSING & SEARCHING
# ============================================================================

@mcp.tool()
def get_frontpage(sort: str = "hot", time_filter: Optional[str] = None) -> Dict[str, Any]:
    """
    Get posts from the front page
    
    Args:
        sort: hot, new, active, top, controversial, most_commented
        time_filter: For top/controversial: hour, day, week, month, year, all
    """
    try:
        page = get_page()
        
        url = f"{BASE_URL}{sort}"
        if time_filter and sort in ["top", "controversial", "most_commented"]:
            url += f"?t={time_filter}"
        
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        
        posts = []
        elements = page.locator(".submission").all()
        
        for elem in elements:
            try:
                title = elem.locator(".submission__title a").text_content().strip()
                link = elem.locator(".submission__title a").get_attribute("href")
                author = elem.locator(".submission__author a").text_content().strip() if elem.locator(".submission__author a").count() > 0 else ""
                forum = elem.locator(".submission__forum a").text_content().strip() if elem.locator(".submission__forum a").count() > 0 else ""
                score = elem.locator(".vote__score").text_content().strip() if elem.locator(".vote__score").count() > 0 else "0"
                
                posts.append({
                    "title": title,
                    "link": link,
                    "author": author,
                    "forum": forum,
                    "score": score
                })
            except:
                continue
        
        return {
            "success": True,
            "sort": sort,
            "posts": posts,
            "count": len(posts)
        }
    
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def browse_forum(
    forum_name: str,
    sort: str = "hot",
    time_filter: Optional[str] = None,
    page_num: int = 1
) -> Dict[str, Any]:
    """
    Browse a specific forum
    
    Args:
        forum_name: Forum name (e.g., "technology", "AskReddit")
        sort: hot, new, active, top, controversial, most_commented
        time_filter: For top/controversial: hour, day, week, month, year, all
        page_num: Page number
    """
    try:
        page = get_page()
        
        url = f"{BASE_URL}f/{forum_name}/{sort}"
        if time_filter and sort in ["top", "controversial", "most_commented"]:
            url += f"?t={time_filter}"
            if page_num > 1:
                url += f"&p={page_num}"
        elif page_num > 1:
            url += f"?p={page_num}"
        
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        
        if page.locator("h1:has-text('Not Found')").count() > 0:
            return {"success": False, "error": f"Forum '{forum_name}' not found"}
        
        posts = []
        elements = page.locator(".submission").all()
        
        for elem in elements:
            try:
                title = elem.locator(".submission__title a").text_content().strip()
                link = elem.locator(".submission__title a").get_attribute("href")
                author = elem.locator(".submission__author a").text_content().strip() if elem.locator(".submission__author a").count() > 0 else ""
                score = elem.locator(".vote__score").text_content().strip() if elem.locator(".vote__score").count() > 0 else "0"
                comments = elem.locator('a[href*="/comment"]').text_content().strip() if elem.locator('a[href*="/comment"]').count() > 0 else "0"
                
                posts.append({
                    "title": title,
                    "link": link,
                    "author": author,
                    "score": score,
                    "comments": comments
                })
            except:
                continue
        
        return {
            "success": True,
            "forum": forum_name,
            "sort": sort,
            "page": page_num,
            "posts": posts,
            "count": len(posts)
        }
    
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def search(options: SearchOptions) -> Dict[str, Any]:
    """
    Search across the site with filters
    
    Example:
        search(SearchOptions(
            query="python",
            forum="technology",
            time="week",
            sort="top"
        ))
    """
    try:
        page = get_page()
        
        url = f"{BASE_URL}search?q={options.query}"
        
        if options.forum:
            url += f"&forum={options.forum}"
        if options.author:
            url += f"&author={options.author}"
        if options.time:
            url += f"&t={options.time}"
        if options.sort != "relevance":
            url += f"&sort={options.sort}"
        if options.page > 1:
            url += f"&p={options.page}"
        
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        
        results = []
        elements = page.locator(".submission, .search-result").all()
        
        for elem in elements:
            try:
                title = elem.locator(".submission__title a").text_content().strip() if elem.locator(".submission__title a").count() > 0 else ""
                link = elem.locator(".submission__title a").get_attribute("href") if elem.locator(".submission__title a").count() > 0 else ""
                author = elem.locator(".submission__author a").text_content().strip() if elem.locator(".submission__author a").count() > 0 else ""
                forum = elem.locator(".submission__forum a").text_content().strip() if elem.locator(".submission__forum a").count() > 0 else ""
                score = elem.locator(".vote__score").text_content().strip() if elem.locator(".vote__score").count() > 0 else "0"
                
                results.append({
                    "title": title,
                    "link": link,
                    "author": author,
                    "forum": forum,
                    "score": score
                })
            except:
                continue
        
        return {
            "success": True,
            "query": options.query,
            "filters": {
                "forum": options.forum,
                "author": options.author,
                "sort": options.sort,
                "time": options.time
            },
            "results": results,
            "count": len(results)
        }
    
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def get_submission(url: str) -> Dict[str, Any]:
    """Get details of a specific submission including comments"""
    try:
        page = get_page()
        
        if not url.startswith("http"):
            url = BASE_URL.rstrip("/") + url
        
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        
        # Get submission details
        title = page.locator("h1.submission__title").text_content().strip() if page.locator("h1.submission__title").count() > 0 else ""
        author = page.locator(".submission__author a").text_content().strip() if page.locator(".submission__author a").count() > 0 else ""
        body = page.locator(".submission__body").text_content().strip() if page.locator(".submission__body").count() > 0 else ""
        score = page.locator(".vote__score").text_content().strip() if page.locator(".vote__score").count() > 0 else "0"
        
        # Get comments
        comments = []
        comment_elements = page.locator(".comment").all()
        
        for elem in comment_elements[:50]:  # Limit to 50 comments
            try:
                comment_author = elem.locator(".comment__author a").text_content().strip() if elem.locator(".comment__author a").count() > 0 else ""
                comment_body = elem.locator(".comment__body").text_content().strip() if elem.locator(".comment__body").count() > 0 else ""
                comment_score = elem.locator(".vote__score").text_content().strip() if elem.locator(".vote__score").count() > 0 else "0"
                
                comments.append({
                    "author": comment_author,
                    "body": comment_body,
                    "score": comment_score
                })
            except:
                continue
        
        return {
            "success": True,
            "title": title,
            "author": author,
            "body": body,
            "score": score,
            "comments": comments,
            "comment_count": len(comments)
        }
    
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================================
# POSTING (Requires Authentication)
# ============================================================================

@mcp.tool()
def create_post(data: SubmissionData) -> Dict[str, Any]:
    """
    Create a new post (requires login)
    
    Example:
        create_post(SubmissionData(
            forum="technology",
            title="Interesting article",
            body="Check this out..."
        ))
    """
    try:
        if not browser_state.get("is_logged_in"):
            return {"success": False, "error": "Must be logged in to post"}
        
        page = get_page()
        
        page.goto(f"{BASE_URL}f/{data.forum}/new", wait_until="domcontentloaded", timeout=30000)
        
        # Fill form
        page.fill('input[name="submission[title]"], input[id*="title"]', data.title)
        
        if data.url:
            page.fill('input[name="submission[url]"], input[id*="url"]', data.url)
        else:
            page.fill('textarea[name="submission[body]"], textarea[id*="body"]', data.body)
        
        page.click('button:has-text("Submit"), button[type="submit"]')
        page.wait_for_load_state("domcontentloaded", timeout=30000)
        
        if page.locator('.alert-danger, .error').count() > 0:
            error_text = page.locator('.alert-danger, .error').first.text_content()
            return {"success": False, "error": error_text.strip()}
        
        return {
            "success": True,
            "message": "Post created",
            "url": page.url
        }
    
    except Exception as e:
        return {"success": False, "error": f"Post creation error: {str(e)}"}


@mcp.tool()
def create_comment(submission_url: str, data: CommentData) -> Dict[str, Any]:
    """
    Add a comment to a post (requires login)
    
    Example:
        create_comment(
            "/f/technology/123/post-title",
            CommentData(body="Great post!")
        ))
    """
    try:
        if not browser_state.get("is_logged_in"):
            return {"success": False, "error": "Must be logged in to comment"}
        
        page = get_page()
        
        if not submission_url.startswith("http"):
            submission_url = BASE_URL.rstrip("/") + submission_url
        
        page.goto(submission_url, wait_until="domcontentloaded", timeout=30000)
        
        # Fill comment form
        page.fill('textarea[name="comment[body]"], textarea[id*="comment"]', data.body)
        page.click('button:has-text("Submit"), button[type="submit"]')
        page.wait_for_load_state("domcontentloaded", timeout=30000)
        
        if page.locator('.alert-danger, .error').count() > 0:
            error_text = page.locator('.alert-danger, .error').first.text_content()
            return {"success": False, "error": error_text.strip()}
        
        return {
            "success": True,
            "message": "Comment posted"
        }
    
    except Exception as e:
        return {"success": False, "error": f"Comment error: {str(e)}"}


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    mcp.run()
