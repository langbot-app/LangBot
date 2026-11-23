"""Keep beta deployment opt-in and consistent across maintained locales."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCALES = ("zh", "en", "ja")
COMPOSE_URL = "https://raw.githubusercontent.com/langbot-app/LangBot/dev/4.11.x/docker/docker-compose.yaml"
BETA_UVX = "uvx --prerelease=allow --refresh langbot==4.11.0b3"


class BetaDeploymentTests(unittest.TestCase):
    def test_docker_beta_covers_all_shared_image_services(self):
        for locale in LOCALES:
            with self.subTest(locale=locale):
                text = (ROOT / locale / "deploy/langbot/docker.mdx").read_text()
                stable, beta = re.split(r"^## Beta[^\n]*\n", text, maxsplit=1, flags=re.MULTILINE)
                self.assertIn("git clone https://github.com/langbot-app/LangBot\ncd LangBot/docker", stable)
                self.assertNotIn("dev/4.11.x", stable)
                self.assertNotIn("rockchin/langbot:beta", stable)
                self.assertIn(COMPOSE_URL, beta)
                self.assertIn("`compose.yaml`", beta)
                self.assertIn("`rockchin/langbot:beta`", beta)
                for service in ("langbot", "langbot_plugin_runtime", "langbot_box"):
                    self.assertIn(f"`{service}`", beta)
                self.assertIn("docker compose --profile all pull\ndocker compose --profile all up -d", beta)
                self.assertLess(beta.index(COMPOSE_URL), beta.index("`rockchin/langbot:beta`"))
                self.assertLess(beta.index("`rockchin/langbot:beta`"), beta.index("docker compose --profile all pull"))

    def test_uvx_beta_allows_transitive_prereleases_and_refreshes(self):
        for locale in LOCALES:
            with self.subTest(locale=locale):
                text = (ROOT / locale / "deploy/langbot/package.mdx").read_text()
                self.assertIn("```bash\nuvx langbot@latest\n```", text)
                self.assertIn(f"```bash\n{BETA_UVX}\n```", text)
                self.assertIn("`--prerelease=allow`", text)
                self.assertIn("`--refresh`", text)
                self.assertEqual(text.count(BETA_UVX), 1)


if __name__ == "__main__":
    unittest.main()
