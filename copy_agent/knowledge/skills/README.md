# Drop-in Skills

Every `.md` file in this folder is loaded into the agent's system prompt on
every chat, after the core knowledge files. To teach the agent a new skill,
add a markdown file here and redeploy (push to master).

Current skills:
- `mindfluence.md` - MindFluence v2.2 cognitive-bias persuasion engine
  (MIT, https://github.com/MADEVAL/MindFluence)

Keep files focused; everything here costs tokens on every message.
