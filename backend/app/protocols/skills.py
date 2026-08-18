"""Agent Skills 注册表:扫描 `backend/skills/<name>/SKILL.md` 并加载。

遵循 Agent Skills 约定:每个技能目录含 SKILL.md,frontmatter 提供
`name` / `description`,正文为技能说明。agent 通过 `load_skill` 工具加载。
"""
from __future__ import annotations

from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parents[2] / "skills"


def _parse_description(skill_md: Path) -> str:
    for line in skill_md.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("description:"):
            return stripped.split(":", 1)[1].strip()
    return ""


def list_skills() -> list[dict]:
    """扫描技能目录,返回 [{name, description}]。"""
    if not SKILLS_DIR.is_dir():
        return []
    out: list[dict] = []
    for d in sorted(SKILLS_DIR.iterdir()):
        f = d / "SKILL.md"
        if f.is_file():
            out.append({"name": d.name, "description": _parse_description(f)})
    return out


def list_skill_names() -> list[str]:
    return [s["name"] for s in list_skills()]


def load_skill(name: str) -> str:
    """读取技能 SKILL.md 内容;不存在抛 KeyError。"""
    f = SKILLS_DIR / name / "SKILL.md"
    if not f.is_file():
        raise KeyError(name)
    return f.read_text(encoding="utf-8")
