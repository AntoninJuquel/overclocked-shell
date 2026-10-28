"""Skills are playbooks Claude follows: they must keep the Ghost voice and only call tools that exist."""
import asyncio
import re
from pathlib import Path

from shell.context import Context
from shell.mcp.server import build_server

ROOT = Path(__file__).resolve().parents[1]
SKILLS = sorted((ROOT / ".claude" / "skills").glob("*/SKILL.md"))


def test_every_skill_links_the_ghost_voice():
    assert SKILLS
    assert [s.parent.name for s in SKILLS if "ghost-voice.md" not in s.read_text(encoding="utf-8")] == []


def test_skill_descriptions_are_english():
    french = re.compile(r"[éèàùçêâîôû]")
    fronts = {s.parent.name: s.read_text(encoding="utf-8").split("---")[1] for s in SKILLS}
    assert [name for name, front in fronts.items() if french.search(front)] == []


def test_skills_name_existing_tools():
    tools = {t.name for t in asyncio.run(build_server(Context()).list_tools())}
    called = {(s.parent.name, name) for s in SKILLS
              for name in re.findall(r"`([a-z_]+)\(", s.read_text(encoding="utf-8"))}
    assert sorted(c for c in called if c[1] not in tools) == []
