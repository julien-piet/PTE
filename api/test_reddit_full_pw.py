"""
Professional Reddit API Tests
Following standard test patterns with proper setup/teardown
"""

from __future__ import annotations

import contextlib
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, Optional

from playwright.sync_api import sync_playwright, Page

from api.reddit_full_pw import (
    register_user, login, logout, browse_forum,
    get_frontpage, get_all_submissions, search,
    RegistrationData, LoginData, SearchOptions
)


# ============================================================================
# BASE TEST CLASS
# ============================================================================

@dataclass
class RedditTest:
    """Base test class for Reddit API tests"""
    query: str = "Test"
    parameters: Optional[Dict[str, str]] = None
    
    def setup_env(self) -> bool:
        """Setup before test - override in subclasses"""
        return True
    
    def check_env(self, result: Optional[Any] = None) -> bool:
        """Run test and check result - override in subclasses"""
        return False
    
    def run(self) -> bool:
        """Execute test with setup and validation"""
        try:
            if not self.setup_env():
                print(f"❌ Setup failed: {self.__class__.__name__}")
                return False
            
            result = self.check_env()
            
            if result:
                print(f"✅ PASSED: {self.__class__.__name__}")
            else:
                print(f"❌ FAILED: {self.__class__.__name__}")
            
            return result
        except Exception as exc:
            print(f"❌ ERROR in {self.__class__.__name__}: {exc}")
            import traceback
            traceback.print_exc()
            return False


# ============================================================================
# HELPER CONTEXT MANAGERS
# ============================================================================

@contextlib.contextmanager
def authenticated_session(username: str, password: str) -> Iterator[None]:
    """
    Context manager for authenticated sessions.
    Logs in on enter, logs out on exit.
    """
    login_result = login(LoginData(username=username, password=password))
    
    if not login_result.get("success"):
        raise RuntimeError(f"Login failed: {login_result.get('error')}")
    
    try:
        yield
    finally:
        logout()


def create_test_user() -> tuple[str, str, str]:
    """
    Create a unique test user and return (username, email, password).
    
    Returns:
        Tuple of (username, email, password)
    """
    timestamp = int(time.time())
    username = f"test_user_{timestamp}"
    email = f"test_{timestamp}@example.com"
    password = "TestPassword123!"
    
    result = register_user(RegistrationData(
        username=username,
        email=email,
        password=password
    ))
    
    if not result.get("success"):
        raise RuntimeError(f"User registration failed: {result.get('error')}")
    
    return username, email, password


# ============================================================================
# AUTHENTICATION TESTS
# ============================================================================

@dataclass
class RegisterNewUserTest(RedditTest):
    """Test: Register a new user account"""
    query: str = "Register new user"
    
    def check_env(self, result: Optional[Any] = None) -> bool:
        """Verify new user can be registered"""
        try:
            timestamp = int(time.time())
            result = register_user(RegistrationData(
                username=f"user_{timestamp}",
                email=f"user_{timestamp}@example.com",
                password="SecurePass123!"
            ))
            
            if result.get("success"):
                print(f"  ✓ User registered: {result.get('username')}")
                return True
            else:
                error = result.get("error", "")
                # Allow "already exists" as success (idempotent test)
                if "already" in error.lower() or "exists" in error.lower():
                    print(f"  ℹ️  User already exists (acceptable)")
                    return True
                print(f"  ✗ Registration failed: {error}")
                return False
        except Exception as exc:
            print(f"  ✗ Exception: {exc}")
            return False


@dataclass
class LoginWithValidCredentialsTest(RedditTest):
    """Test: Login with valid credentials"""
    query: str = "Login with valid credentials"
    
    def setup_env(self) -> bool:
        """Create a test user to login with"""
        try:
            self._username, self._email, self._password = create_test_user()
            print(f"  ℹ️  Created test user: {self._username}")
            return True
        except Exception as exc:
            print(f"  ✗ Failed to create test user: {exc}")
            return False
    
    def check_env(self, result: Optional[Any] = None) -> bool:
        """Verify login succeeds"""
        try:
            result = login(LoginData(
                username=self._username,
                password=self._password
            ))
            
            if result.get("success"):
                print(f"  ✓ Login successful: {result.get('username')}")
                # Cleanup: logout after test
                logout()
                return True
            else:
                print(f"  ✗ Login failed: {result.get('error')}")
                return False
        except Exception as exc:
            print(f"  ✗ Exception: {exc}")
            return False


@dataclass
class LogoutTest(RedditTest):
    """Test: Logout functionality"""
    query: str = "Logout current user"
    
    def setup_env(self) -> bool:
        """Login before testing logout"""
        try:
            self._username, self._email, self._password = create_test_user()
            login_result = login(LoginData(
                username=self._username,
                password=self._password
            ))
            return login_result.get("success", False)
        except Exception as exc:
            print(f"  ✗ Setup failed: {exc}")
            return False
    
    def check_env(self, result: Optional[Any] = None) -> bool:
        """Verify logout succeeds"""
        try:
            result = logout()
            
            if result.get("success"):
                print(f"  ✓ Logout successful")
                return True
            else:
                print(f"  ✗ Logout failed: {result.get('error')}")
                return False
        except Exception as exc:
            print(f"  ✗ Exception: {exc}")
            return False


# ============================================================================
# BROWSING TESTS
# ============================================================================

@dataclass
class BrowseForumTest(RedditTest):
    """Test: Browse a specific forum"""
    query: str = "Browse r/{{forum}}"
    parameters: Optional[Dict[str, str]] = field(
        default_factory=lambda: {"forum": "technology"}
    )
    
    def check_env(self, result: Optional[Any] = None) -> bool:
        """Verify forum browsing returns posts"""
        try:
            forum = self.parameters["forum"]
            result = browse_forum(forum_name=forum, sort="hot")
            
            if result.get("success"):
                count = result.get("count", 0)
                print(f"  ✓ Found {count} posts in r/{forum}")
                
                if count > 0:
                    first = result["posts"][0]
                    print(f"  ✓ Top: '{first['title'][:50]}...'")
                    return True
                else:
                    print(f"  ℹ️  Forum is empty (acceptable)")
                    return True
            else:
                print(f"  ✗ Failed: {result.get('error')}")
                return False
        except Exception as exc:
            print(f"  ✗ Exception: {exc}")
            return False


@dataclass
class GetAllSubmissionsTest(RedditTest):
    """Test: Get all submissions from frontpage"""
    query: str = "Get all submissions"
    
    def check_env(self, result: Optional[Any] = None) -> bool:
        """Verify getting all submissions works"""
        try:
            result = get_all_submissions(sort="hot")
            
            if result.get("success"):
                count = result.get("count", 0)
                print(f"  ✓ Found {count} submissions")
                
                if count > 0:
                    first = result["posts"][0]
                    print(f"  ✓ Top: '{first['title'][:50]}...'")
                
                return count > 0
            else:
                print(f"  ✗ Failed: {result.get('error')}")
                return False
        except Exception as exc:
            print(f"  ✗ Exception: {exc}")
            return False


@dataclass
class SearchWithFiltersTest(RedditTest):
    """Test: Search with filters"""
    query: str = "Search for {{query}} in r/{{forum}}"
    parameters: Optional[Dict[str, str]] = field(
        default_factory=lambda: {"query": "AI", "forum": "technology"}
    )
    
    def check_env(self, result: Optional[Any] = None) -> bool:
        """Verify search with filters works"""
        try:
            result = search(SearchOptions(
                query=self.parameters["query"],
                forum=self.parameters["forum"],
                sort="relevance"
            ))
            
            if result.get("success"):
                count = result.get("count", 0)
                print(f"  ✓ Found {count} results")
                
                if count > 0:
                    first = result["results"][0]
                    print(f"  ✓ Top: '{first['title'][:50]}...'")
                
                return True  # Pass even if 0 results
            else:
                print(f"  ✗ Failed: {result.get('error')}")
                return False
        except Exception as exc:
            print(f"  ✗ Exception: {exc}")
            return False


# ============================================================================
# INTEGRATED WORKFLOW TESTS
# ============================================================================

@dataclass
class CompleteUserWorkflowTest(RedditTest):
    """
    Test: Complete user workflow
    Register -> Login -> Browse -> Logout
    """
    query: str = "Complete user workflow"
    
    def check_env(self, result: Optional[Any] = None) -> bool:
        """Test complete user workflow"""
        try:
            # Step 1: Register
            print(f"  [1/4] Registering user...")
            username, email, password = create_test_user()
            print(f"  ✓ Registered: {username}")
            
            # Step 2: Login
            print(f"  [2/4] Logging in...")
            with authenticated_session(username, password):
                print(f"  ✓ Logged in")
                
                # Step 3: Browse
                print(f"  [3/4] Browsing forum...")
                browse_result = browse_forum(forum_name="technology", sort="hot")
                
                if browse_result.get("success"):
                    count = browse_result.get("count", 0)
                    print(f"  ✓ Browsed forum ({count} posts)")
                else:
                    print(f"  ✗ Browse failed")
                    return False
            
            # Step 4: Logout (happens automatically via context manager)
            print(f"  [4/4] Logged out")
            print(f"  ✓ Complete workflow succeeded")
            
            return True
            
        except Exception as exc:
            print(f"  ✗ Workflow failed: {exc}")
            return False


# ============================================================================
# TEST SUITE RUNNER
# ============================================================================

def run_professional_tests():
    """Run all professional-style tests"""
    
    print("\n" + "="*70)
    print(" REDDIT API - PROFESSIONAL TEST SUITE")
    print("="*70)
    print()
    
    # Define test groups
    auth_tests = [
        RegisterNewUserTest(),
        LoginWithValidCredentialsTest(),
        LogoutTest(),
    ]
    
    browsing_tests = [
        BrowseForumTest(),
        GetAllSubmissionsTest(),
        SearchWithFiltersTest(),
    ]
    
    workflow_tests = [
        CompleteUserWorkflowTest(),
    ]
    
    # Run tests by category
    results = {"passed": 0, "failed": 0}
    
    print("="*70)
    print(" AUTHENTICATION TESTS")
    print("="*70)
    print()
    
    for test in auth_tests:
        if test.run():
            results["passed"] += 1
        else:
            results["failed"] += 1
        print()
    
    print("="*70)
    print(" BROWSING TESTS")
    print("="*70)
    print()
    
    for test in browsing_tests:
        if test.run():
            results["passed"] += 1
        else:
            results["failed"] += 1
        print()
    
    print("="*70)
    print(" WORKFLOW TESTS")
    print("="*70)
    print()
    
    for test in workflow_tests:
        if test.run():
            results["passed"] += 1
        else:
            results["failed"] += 1
        print()
    
    # Summary
    total = results["passed"] + results["failed"]
    print("="*70)
    print(" TEST SUMMARY")
    print("="*70)
    print(f"\n✅ Passed: {results['passed']}/{total}")
    print(f"❌ Failed: {results['failed']}/{total}")
    
    if results["failed"] == 0:
        print("\n🎉 All tests passed!")
    else:
        print(f"\n⚠️  {results['failed']} test(s) failed")
    
    success_rate = (results['passed'] / total * 100) if total > 0 else 0
    print(f"Success Rate: {success_rate:.1f}%\n")
    
    return results


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    from api.reddit_full_pw import cleanup_browser
    
    try:
        results = run_professional_tests()
        exit(0 if results["failed"] == 0 else 1)
    finally:
        print("Cleaning up browser...")
        cleanup_browser()
        print("✓ Done!\n")
