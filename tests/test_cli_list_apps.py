
import subprocess
import unittest

class TestCLI(unittest.TestCase):
    def test_list_apps(self):
        # Run the command and capture output
        result = subprocess.run(
            ['python', '-m', 'gum.cli', '--list-apps'],
            capture_output=True,
            text=True
        )
        
        # Check that it exited successfully
        self.assertEqual(result.returncode, 0)
        
        # Check that it printed the expected header
        self.assertIn("Visible applications:", result.stdout)
        
        # Check that it found at least some apps (assuming something is open during tests)
        # In a headless CI environment this might be empty, but locally it should have items.
        lines = result.stdout.strip().split('\n')
        # Header + at least one app
        self.assertGreaterEqual(len(lines), 2)

    def test_list_apps_with_user(self):
        # Run with -u but use a mock or just check it starts
        # We use a timeout since listening mode runs forever
        try:
            result = subprocess.run(
                ['python', '-m', 'gum.cli', '--list-apps', '-u', 'TestUser'],
                capture_output=True,
                text=True,
                timeout=5 # Give it enough time to list apps and start listening
            )
        except subprocess.TimeoutExpired as e:
            # This is actually what we expect if it doesn't return!
            stdout = e.stdout.decode() if e.stdout else ""
            self.assertIn("Visible applications:", stdout)
            self.assertIn("Listening to TestUser", stdout)
            return

        # If it didn't timeout, it exited early, which might be an error if listening failed
        self.assertIn("Visible applications:", result.stdout)
        self.assertIn("Listening to TestUser", result.stdout)

if __name__ == '__main__':
    unittest.main()
