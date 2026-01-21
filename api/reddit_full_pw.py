"""
Reddit API Core Functions - No MCP Decorators
Test-friendly version for direct Python calls
"""

from typing import Dict, Any, Optional
from pydantic import BaseModel, Field, EmailStr
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

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
    """Get or create browser page"""
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


def cleanup_browser() -> Dict[str, Any]:
    """Close browser and clean up"""
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
# MODELS
# ============================================================================

class RegistrationData(BaseModel):
    username: str
    email: EmailStr
    password: str


class LoginData(BaseModel):
    username: str
    password: str
    remember_me: bool = True


class SubmissionData(BaseModel):
    forum: str
    title: str
    body: Optional[str] = ""
    url: Optional[str] = None


class CommentData(BaseModel):
    body: str


class SearchOptions(BaseModel):
    query: str
    forum: Optional[str] = None
    author: Optional[str] = None
    sort: str = "relevance"
    time: Optional[str] = None
    type: str = "submissions"
    page: int = 1


# ============================================================================
# AUTHENTICATION
# ============================================================================

def register_user(data: RegistrationData) -> Dict[str, Any]:
    """Register a new user"""
    try:
        print(f"  [DEBUG] Starting registration for: {data.username}")
        page = get_page()
        
        print(f"  [DEBUG] Navigating to registration page...")
        page.goto(f"{BASE_URL}registration", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(500)
        print(f"  [DEBUG] Current URL: {page.url}")
        print(f"  [DEBUG] Page title: {page.title()}")
        
        print(f"  [DEBUG] Filling username field...")
        page.fill('input[name="user[username]"]', data.username)
        
        print(f"  [DEBUG] Filling email field...")
        page.fill('input[name="user[email]"]', data.email)
        
        print(f"  [DEBUG] Filling password fields...")
        page.fill('input[name="user[password][first]"]', data.password)
        page.fill('input[name="user[password][second]"]', data.password)
        
        print(f"  [DEBUG] Clicking submit button...")
        page.click('button:has-text("Sign up")')
        
        print(f"  [DEBUG] Waiting for response...")
        page.wait_for_load_state("domcontentloaded", timeout=30000)
        
        print(f"  [DEBUG] After submit URL: {page.url}")
        
        # Check for errors
        error_count = page.locator('.alert-danger, .error').count()
        print(f"  [DEBUG] Error elements found: {error_count}")
        
        if error_count > 0:
            error_text = page.locator('.alert-danger, .error').first.text_content()
            print(f"  [DEBUG] Error message: {error_text.strip()}")
            return {"success": False, "error": error_text.strip()}
        
        # Check if still on registration page
        if "registration" in page.url.lower():
            print(f"  [DEBUG] Still on registration page - checking for validation errors...")
            
            # Check for any visible text on page that might indicate the issue
            body_text = page.locator("body").text_content()
            if "username" in body_text.lower() and "taken" in body_text.lower():
                print(f"  [DEBUG] Username appears to be taken")
                return {"success": False, "error": "Username already taken"}
            
            if "email" in body_text.lower() and ("taken" in body_text.lower() or "exists" in body_text.lower()):
                print(f"  [DEBUG] Email appears to be taken")
                return {"success": False, "error": "Email already exists"}
            
            print(f"  [DEBUG] Generic registration failure - page content sample:")
            print(f"  [DEBUG] {body_text[:500]}")
            
            return {"success": False, "error": "Registration failed - still on registration page"}
        
        print(f"  [DEBUG] Registration appears successful - redirected to: {page.url}")
        return {"success": True, "message": "Registration successful", "username": data.username}
    
    except Exception as e:
        print(f"  [DEBUG] Exception occurred: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": f"Registration error: {str(e)}"}


def login(data: LoginData) -> Dict[str, Any]:
    """Log in a user"""
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
        
        return {"success": True, "message": "Login successful", "username": data.username}
    except Exception as e:
        return {"success": False, "error": f"Login error: {str(e)}"}


def logout() -> Dict[str, Any]:
    """Log out"""
    try:
        print(f"  [DEBUG] Checking login status...")
        if not browser_state.get("is_logged_in"):
            print(f"  [DEBUG] Not logged in according to browser_state")
            return {"success": False, "error": "Not logged in"}
        
        page = get_page()
        print(f"  [DEBUG] Current URL: {page.url}")
        
        # The logout button is in a hidden dropdown menu
        # We need to click the user menu first to make it visible
        print(f"  [DEBUG] Looking for user menu to open...")
        
        # Try to find and click the user menu/dropdown
        menu_selectors = [
            'button.site-nav__mobile-toggle',  # Mobile menu toggle
            '.dropdown__toggle',  # Dropdown toggle
            'button:has-text("' + (browser_state.get("username") or "") + '")',  # Username button
            '.site-nav__link.dropdown__toggle',  # Nav dropdown
        ]
        
        menu_opened = False
        for selector in menu_selectors:
            print(f"  [DEBUG] Trying menu selector: {selector}")
            menu_elem = page.locator(selector)
            count = menu_elem.count()
            print(f"  [DEBUG]   Found {count} elements")
            
            if count > 0:
                # Check if it's visible
                if menu_elem.first.is_visible():
                    print(f"  [DEBUG] Clicking menu to open dropdown...")
                    menu_elem.first.click()
                    page.wait_for_timeout(500)  # Wait for menu to open
                    menu_opened = True
                    break
        
        if not menu_opened:
            print(f"  [DEBUG] Could not find visible user menu, trying direct logout...")
        
        # Now try to click logout button (should be visible now)
        print(f"  [DEBUG] Looking for logout button...")
        
        logout_selectors = [
            'button:has-text("Log out")',
            'a:has-text("Log out")',
            'a[href*="logout"]',
            'a:has-text("Logout")',
            'a:has-text("Sign out")',
        ]
        
        for selector in logout_selectors:
            print(f"  [DEBUG] Trying logout selector: {selector}")
            elem = page.locator(selector)
            count = elem.count()
            print(f"  [DEBUG]   Found {count} elements")
            
            if count > 0:
                # Force click even if not visible (using force option)
                print(f"  [DEBUG] Attempting to click logout (with force)...")
                try:
                    elem.first.click(force=True, timeout=5000)
                    page.wait_for_load_state("domcontentloaded")
                    
                    browser_state["is_logged_in"] = False
                    browser_state["username"] = None
                    
                    print(f"  [DEBUG] Logout successful!")
                    return {"success": True, "message": "Logged out successfully"}
                except Exception as click_error:
                    print(f"  [DEBUG] Click failed: {click_error}")
                    continue
        
        print(f"  [DEBUG] Could not click logout button")
        return {"success": False, "error": "Could not click logout button"}
        
    except Exception as e:
        print(f"  [DEBUG] Exception in logout: {type(e).__name__}: {e}")
        return {"success": False, "error": f"Logout error: {str(e)}"}


def check_login_status() -> Dict[str, Any]:
    """Check login status"""
    return {
        "is_logged_in": browser_state.get("is_logged_in", False),
        "username": browser_state.get("username")
    }


# ============================================================================
# BROWSING
# ============================================================================

def get_frontpage(sort: str = "hot", time_filter: Optional[str] = None, scope: str = "featured") -> Dict[str, Any]:
    """
    Get frontpage posts
    
    Args:
        sort: hot, new, top, controversial, most_commented
        time_filter: For top/controversial: hour, day, week, month, year, all
        scope: "featured" (default) or "all" - whether to show featured forums or all submissions
    """
    try:
        print(f"  [DEBUG] Getting frontpage with sort={sort}, time_filter={time_filter}, scope={scope}")
        page = get_page()
        
        # Build URL based on scope
        if scope == "all":
            url = f"{BASE_URL}all/{sort}"
        else:
            # Featured (default)
            if sort == "hot":
                url = f"{BASE_URL}"
            else:
                url = f"{BASE_URL}{sort}"
        
        if time_filter and sort in ["top", "controversial", "most_commented"]:
            url += f"?t={time_filter}"
        
        print(f"  [DEBUG] Navigating to: {url}")
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        
        print(f"  [DEBUG] Current URL: {page.url}")
        print(f"  [DEBUG] Page title: {page.title()}")
        
        # Check for submissions
        print(f"  [DEBUG] Looking for .submission elements...")
        submission_locator = page.locator(".submission")
        count = submission_locator.count()
        print(f"  [DEBUG] Found {count} .submission elements")
        
        if count == 0 and scope == "featured":
            # Check if page says "no featured forums"
            body_text = page.locator("body").text_content()
            if "no featured forums" in body_text.lower():
                print(f"  [DEBUG] No featured forums - try scope='all' to see all submissions")
                return {
                    "success": True,
                    "sort": sort,
                    "scope": scope,
                    "posts": [],
                    "count": 0,
                    "note": "No featured forums. Try get_frontpage(scope='all') or get_all_submissions()"
                }
            
            print(f"  [DEBUG] No submissions found, but no clear reason why")
        
        posts = []
        elements = submission_locator.all()
        
        print(f"  [DEBUG] Processing {len(elements)} submission elements...")
        
        for i, elem in enumerate(elements):
            try:
                print(f"  [DEBUG] Processing post {i+1}...")
                
                title_elem = elem.locator(".submission__title a")
                title_count = title_elem.count()
                print(f"  [DEBUG]   Title elements: {title_count}")
                
                if title_count == 0:
                    print(f"  [DEBUG]   Skipping - no title found")
                    continue
                
                title = title_elem.text_content().strip()
                link = title_elem.get_attribute("href")
                
                author = ""
                author_elem = elem.locator(".submission__author a")
                if author_elem.count() > 0:
                    author = author_elem.text_content().strip()
                
                forum = ""
                forum_elem = elem.locator(".submission__forum a")
                if forum_elem.count() > 0:
                    forum = forum_elem.text_content().strip()
                
                score = "0"
                score_elem = elem.locator(".vote__score")
                if score_elem.count() > 0:
                    score = score_elem.text_content().strip()
                
                print(f"  [DEBUG]   Post: '{title[:50]}...'")
                
                posts.append({"title": title, "link": link, "author": author, "forum": forum, "score": score})
            except Exception as e:
                print(f"  [DEBUG]   Error processing post {i+1}: {e}")
                continue
        
        print(f"  [DEBUG] Successfully extracted {len(posts)} posts")
        
        return {"success": True, "sort": sort, "scope": scope, "posts": posts, "count": len(posts)}
    except Exception as e:
        print(f"  [DEBUG] Exception in get_frontpage: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


def get_all_submissions(sort: str = "hot", time_filter: Optional[str] = None) -> Dict[str, Any]:
    """
    Get ALL submissions from all forums (not just featured)
    
    This is a convenience function that calls get_frontpage(scope="all")
    
    Args:
        sort: hot, new, top, controversial, most_commented
        time_filter: For top/controversial: hour, day, week, month, year, all
    
    Example:
        posts = get_all_submissions(sort="hot")
        posts = get_all_submissions(sort="top", time_filter="week")
    """
    return get_frontpage(sort=sort, time_filter=time_filter, scope="all")


def browse_forum(forum_name: str, sort: str = "hot", time_filter: Optional[str] = None, page_num: int = 1) -> Dict[str, Any]:
    """Browse a forum"""
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
                
                posts.append({"title": title, "link": link, "author": author, "score": score, "comments": comments})
            except:
                continue
        
        return {"success": True, "forum": forum_name, "sort": sort, "page": page_num, "posts": posts, "count": len(posts)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_submission(url: str) -> Dict[str, Any]:
    """Get submission details"""
    try:
        page = get_page()
        
        if not url.startswith("http"):
            url = BASE_URL.rstrip("/") + url
        
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        
        title = page.locator("h1.submission__title").text_content().strip() if page.locator("h1.submission__title").count() > 0 else ""
        author = page.locator(".submission__author a").text_content().strip() if page.locator(".submission__author a").count() > 0 else ""
        body = page.locator(".submission__body").text_content().strip() if page.locator(".submission__body").count() > 0 else ""
        score = page.locator(".vote__score").text_content().strip() if page.locator(".vote__score").count() > 0 else "0"
        
        comments = []
        comment_elements = page.locator(".comment").all()
        
        for elem in comment_elements[:50]:
            try:
                comment_author = elem.locator(".comment__author a").text_content().strip() if elem.locator(".comment__author a").count() > 0 else ""
                comment_body = elem.locator(".comment__body").text_content().strip() if elem.locator(".comment__body").count() > 0 else ""
                comment_score = elem.locator(".vote__score").text_content().strip() if elem.locator(".vote__score").count() > 0 else "0"
                
                comments.append({"author": comment_author, "body": comment_body, "score": comment_score})
            except:
                continue
        
        return {"success": True, "title": title, "author": author, "body": body, "score": score, "comments": comments, "comment_count": len(comments)}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================================
# SEARCH
# ============================================================================

def search(options: SearchOptions) -> Dict[str, Any]:
    """Search with filters"""
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
                
                results.append({"title": title, "link": link, "author": author, "forum": forum, "score": score})
            except:
                continue
        
        return {
            "success": True,
            "query": options.query,
            "filters": {"forum": options.forum, "author": options.author, "sort": options.sort, "time": options.time},
            "results": results,
            "count": len(results)
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================================
# POSTING
# ============================================================================

def create_post(data: SubmissionData) -> Dict[str, Any]:
    """Create a post"""
    try:
        if not browser_state.get("is_logged_in"):
            return {"success": False, "error": "Must be logged in"}
        
        page = get_page()
        page.goto(f"{BASE_URL}f/{data.forum}/new", wait_until="domcontentloaded", timeout=30000)
        
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
        
        return {"success": True, "message": "Post created", "url": page.url}
    except Exception as e:
        return {"success": False, "error": f"Post creation error: {str(e)}"}


def create_comment(submission_url: str, data: CommentData) -> Dict[str, Any]:
    """Add a comment"""
    try:
        if not browser_state.get("is_logged_in"):
            return {"success": False, "error": "Must be logged in"}
        
        page = get_page()
        
        if not submission_url.startswith("http"):
            submission_url = BASE_URL.rstrip("/") + submission_url
        
        page.goto(submission_url, wait_until="domcontentloaded", timeout=30000)
        
        page.fill('textarea[name="comment[body]"], textarea[id*="comment"]', data.body)
        page.click('button:has-text("Submit"), button[type="submit"]')
        page.wait_for_load_state("domcontentloaded", timeout=30000)
        
        if page.locator('.alert-danger, .error').count() > 0:
            error_text = page.locator('.alert-danger, .error').first.text_content()
            return {"success": False, "error": error_text.strip()}
        
        return {"success": True, "message": "Comment posted"}
    except Exception as e:
        return {"success": False, "error": f"Comment error: {str(e)}"}
