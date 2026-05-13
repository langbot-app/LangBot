---
name: create-skill
description: Create new skills for LangBot. Use when users want to create, modify, or register a skill. Helps draft SKILL.md with proper frontmatter and register skills from sandbox directories.
---

# Create Skill

A skill for creating new LangBot skills.

## Skill Structure

A skill is a directory containing, at minimum, a `SKILL.md` file:

```
skill-name/
├── SKILL.md          # Required: metadata + instructions
├── scripts/          # Optional: helper scripts
├── references/       # Optional: documentation
├── assets/           # Optional: templates, resources
```

## SKILL.md Format

SKILL.md must contain YAML frontmatter followed by Markdown content:

```markdown
---
name: skill-name
display_name: Skill Display Name
description: What this skill does and when to use it.
---

# Skill Title

Instructions for how to use this skill...

## Examples

- Example 1
- Example 2
```

### Frontmatter Fields

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Skill identifier. 1-64 chars, lowercase letters, numbers, hyphens only. Must not start or end with hyphen. |
| `display_name` | No | Human-readable name shown in UI. |
| `description` | Yes | What the skill does and when to use it. Max 1024 chars. Include keywords for triggering. |
| `license` | No | License name or reference. |
| `metadata` | No | Additional key-value metadata. |

### Body Content

The Markdown body contains skill instructions. Recommended sections:
- Step-by-step instructions
- Examples
- Common edge cases
- Guidelines

Keep SKILL.md under 500 lines. Move detailed content to `references/` directory.

## Creating a Skill

1. **Understand requirements**: Ask what the skill should do
2. **Draft SKILL.md**: Create frontmatter + instructions
3. **Create in sandbox**: Write files to `/workspace/{skill-name}/`
4. **Register**: Use `register_skill` tool to register to LangBot store

### Name Rules

- Lowercase letters, numbers, hyphens only
- Cannot start or end with hyphen
- No consecutive hyphens (`--`)
- 1-64 characters

Valid: `pdf-processing`, `data-analysis`, `code-review`
Invalid: `PDF-Processing`, `-pdf`, `pdf--processing`

### Description Tips

Good description describes both what and when:
```yaml
description: Extracts text from PDF files. Use when working with PDF documents or when user mentions PDFs.
```

Poor description:
```yaml
description: Helps with PDFs.
```

## Workflow Example

1. User: "Create a skill for generating reports"
2. Ask clarifying questions about report format, templates, etc.
3. Create `/workspace/report-generator/SKILL.md`
4. Optionally create helper scripts in `/workspace/report-generator/scripts/`
5. Call `register_skill(path="/workspace/report-generator", name="report-generator")`
6. Skill is now available via `activate(skill_name="report-generator")`

## After Registration

The skill package is copied to `data/skills/` and loaded by LangBot.
User can activate it immediately with the `activate` tool.