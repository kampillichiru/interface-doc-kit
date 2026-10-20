"""Tests of `doc.py install`: one standard kit copied into a project, with a backup of what it replaces.
Run from the tools folder: python -m unittest discover tests"""

import io
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dockit import cli, install  # noqa: E402


class InstallTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *args):
        out = io.StringIO()
        with redirect_stdout(out):
            code = cli.main(["install", str(self.project), *args])
        return code, out.getvalue()

    def write(self, rel, text):
        path = self.project / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def test_fresh_install_then_standard(self):
        code, _ = self.run_cli()
        self.assertEqual(code, 0)
        for rel in (".github/agents/doc-explainer.agent.md", ".github/doc-kit/steps/0-rules.md",
                    ".github/prompts/doc-run.prompt.md", ".github/skills/ask-the-docs/SKILL.md",
                    ".github/copilot-instructions.md", "doc-input/module.md"):
            self.assertTrue((self.project / rel).exists(), rel)
        self.assertFalse(list(self.project.rglob("__pycache__")))
        self.assertFalse((self.project / install.BACKUP_DIR).exists())
        code, out = self.run_cli("--check")
        self.assertEqual(code, 0)
        self.assertIn("already on the standard kit", out)

    def test_old_kit_is_replaced_and_backed_up(self):
        self.write(".github/agents/doc-output-tracer.agent.md", "old agent")
        self.write(".github/doc-kit/steps/03-trace-output.md", "old step")
        self.write(".github/doc-kit/steps/0-rules.md", "old rules")
        self.write(".github/agents/team-helper.agent.md", "the project's own agent")
        code, out = self.run_cli("--check")
        self.assertEqual(code, 1)
        self.assertIn("remove: .github/agents/doc-output-tracer.agent.md", out)
        self.assertTrue((self.project / ".github/agents/doc-output-tracer.agent.md").exists())  # check changes nothing

        self.run_cli()
        self.assertFalse((self.project / ".github/agents/doc-output-tracer.agent.md").exists())
        self.assertFalse((self.project / ".github/doc-kit/steps/03-trace-output.md").exists())
        self.assertEqual((self.project / ".github/agents/team-helper.agent.md").read_text(), "the project's own agent")
        backup = next((self.project / install.BACKUP_DIR).iterdir())
        self.assertEqual((backup / ".github/agents/doc-output-tracer.agent.md").read_text(), "old agent")
        self.assertEqual((backup / ".github/doc-kit/steps/0-rules.md").read_text(), "old rules")
        self.assertTrue(install.plan(self.project).standard)

    def test_a_project_keeps_its_own_models(self):
        self.run_cli()
        agent = self.project / ".github/agents/doc-explainer.agent.md"
        text = agent.read_text(encoding="utf-8")
        agent.write_text(re.sub(r"^model:.*$", "model: ['Our Model (copilot)']", text, flags=re.M), encoding="utf-8")
        self.assertTrue(install.plan(self.project).standard)  # a model choice is not a difference
        (self.project / ".github/doc-kit/steps/0-rules.md").write_text("old", encoding="utf-8")
        (self.project / ".github/agents/doc-explainer.agent.md").write_text(
            agent.read_text(encoding="utf-8").replace("You do one step", "You do a step"), encoding="utf-8")
        self.run_cli()
        updated = agent.read_text(encoding="utf-8")
        self.assertIn("model: ['Our Model (copilot)']", updated)
        self.assertIn("You do one step", updated)  # the rest of the agent is the kit's

    def test_project_instructions_are_kept(self):
        path = self.write(".github/copilot-instructions.md", "# Our project\n\nUse tabs.\n")
        self.run_cli()
        text = path.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("# Our project\n\nUse tabs.\n"))
        self.assertIn(install.BLOCK_START, text)
        self.run_cli()  # a second install changes nothing
        self.assertEqual(path.read_text(encoding="utf-8"), text)

    def test_project_lines_after_an_old_kit_text_are_kept(self):
        path = self.write(".github/copilot-instructions.md", "# Documentation kit\n\nold text\n\n## Our team rules\n\nUse tabs.\n")
        self.run_cli()
        text = path.read_text(encoding="utf-8")
        self.assertNotIn("old text", text)
        self.assertIn("## Our team rules\n\nUse tabs.", text)

    def test_old_kit_instructions_are_replaced(self):
        path = self.write(".github/copilot-instructions.md", "# Documentation kit\n\nold text\n")
        self.run_cli()
        text = path.read_text(encoding="utf-8")
        self.assertNotIn("old text", text)
        self.assertTrue(text.startswith(install.BLOCK_START))

    def test_input_and_output_are_never_overwritten(self):
        module = self.write("doc-input/module.md", "our module")
        result = self.write("doc-output/SHOP/SHOP-documentation.md", "our document")
        self.run_cli()
        self.assertEqual(module.read_text(), "our module")
        self.assertEqual(result.read_text(), "our document")
        self.assertTrue((self.project / "doc-input/glossary.csv").exists())  # missing template added

    def test_refuses_the_kit_itself(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = cli.main(["install", str(install.KIT_ROOT)])
        self.assertEqual(code, 2)
        self.assertIn("the kit itself", out.getvalue())


if __name__ == "__main__":
    unittest.main()
