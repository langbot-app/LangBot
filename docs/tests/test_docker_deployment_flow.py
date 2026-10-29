"""Keep the beginner Docker guide portable, short, and ordered."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class DockerDeploymentFlowTests(unittest.TestCase):
    def test_all_locales_follow_one_setup_path(self):
        for locale in ("zh", "en", "ja"):
            with self.subTest(locale=locale):
                text = (ROOT / locale / "deploy/langbot/docker.mdx").read_text().split("\n## Beta", 1)[0]
                headings = re.findall(r"^## (\d+)\. .+$", text, re.MULTILINE)
                self.assertEqual(headings, ["1", "2", "3", "4"])
                download = "git clone https://github.com/langbot-app/LangBot\ncd LangBot/docker"
                start = "docker compose --profile all up -d"
                mirror = "docker.langbot.app/langbot-public/rockchin/langbot:latest"
                self.assertIn(download, text)
                self.assertEqual(text.count(start), 1)
                self.assertLess(text.index(download), text.index(mirror))
                self.assertLess(text.index(mirror), text.index(start))
                self.assertLess(text.index(start), text.index("http://localhost:5300"))
                self.assertLess(text.index("`/root`"), text.index(download))
                self.assertIn("`/etc`", text)
                for removed in ("seekdb", "langbot_box_root", "openssl", "control_token", "<accordion"):
                    self.assertNotIn(removed, text.lower())

    def test_common_commands_are_editable_and_not_linux_only(self):
        for locale in ("zh", "en", "ja"):
            with self.subTest(locale=locale):
                text = (ROOT / locale / "deploy/langbot/docker.mdx").read_text().split("\n## Beta", 1)[0]
                for platform in ("Windows", "macOS", "Linux", "PowerShell", "Docker Desktop"):
                    self.assertIn(platform, text)
                commands = re.findall(r"```bash\n(.*?)\n```", text, re.DOTALL)
                self.assertEqual(commands, [
                    "git clone https://github.com/langbot-app/LangBot\ncd LangBot/docker",
                    "docker compose --profile all up -d",
                ])
                for nonportable in ("&&", "cd /opt", "export ", "sudo "):
                    self.assertNotIn(nonportable, "\n".join(commands))
                self.assertLess(text.index("<Note>"), text.index("docker compose --profile all up -d"))
                for target in ("usage/models/readme", "usage/platforms/readme"):
                    self.assertIn(f"/{locale}/{target}", text)


if __name__ == "__main__":
    unittest.main()
