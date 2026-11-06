# Prompts

Dylan's personal skills, packaged as a Claude plugin marketplace. The repo is both the marketplace and its single plugin (`prompts`).

## Layout

- `skills/<name>/SKILL.md` - one skill per folder, with `name` and `description` frontmatter
- `.claude-plugin/marketplace.json` - marketplace definition
- `.claude-plugin/plugin.json` - plugin manifest
- `.cursor/skills` - symlink to `skills/` so Cursor sees the same skills

## Sync with Claude Desktop (Cowork)

1. Plugins page -> **Add marketplace** -> `earthastronaut/prompts`
2. Install the `prompts` plugin.
3. After pushing changes, click **Update** on the marketplace. Sync is a manual pull, not automatic.

## Claude Code

```
/plugin marketplace add earthastronaut/prompts
/plugin install prompts@prompts
```

## Add a skill

1. Create `skills/<name>/SKILL.md`:

   ```markdown
   ---
   name: <name>
   description: What it does and when to use it.
   ---
   # Title

   Instructions...
   ```

2. Commit and push to `main`.
3. Click **Update** in Cowork (or `/plugin marketplace update prompts` in Claude Code).
