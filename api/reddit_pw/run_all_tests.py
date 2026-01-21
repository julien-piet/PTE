"""Run all reddit_pw unit tests."""

import sys
import unittest
from pathlib import Path

# Add parent directory to path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Import all test modules
from api.reddit_pw import login_tests
from api.reddit_pw import registration_tests
from api.reddit_pw import logout_tests
from api.reddit_pw import browse_tests
from api.reddit_pw import search_tests


def run_all_tests():
    """Run all unit tests and report results."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test modules
    suite.addTests(loader.loadTestsFromModule(login_tests))
    suite.addTests(loader.loadTestsFromModule(registration_tests))
    suite.addTests(loader.loadTestsFromModule(logout_tests))
    suite.addTests(loader.loadTestsFromModule(browse_tests))
    suite.addTests(loader.loadTestsFromModule(search_tests))
    
    # Run tests with verbose output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*70)
    print(" TEST SUMMARY")
    print("="*70)
    print(f"\nTests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    if result.wasSuccessful():
        print("\n✅ All unit tests passed!")
        return 0
    else:
        print("\n❌ Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
