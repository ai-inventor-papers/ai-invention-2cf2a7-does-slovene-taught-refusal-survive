# tools

Helper scripts from the AI Inventor platform's own skills, copied here because
a published script imports or runs them. The scripts that use them name this
folder in place of the platform's `.claude/skills/<skill>`.

On the platform, a shell step may run a helper with the platform's
`.ability_client_venv/bin/python`, which is not part of this repository. Run
it with any Python 3.12 that has the packages the helper imports instead.
Each helper runs standalone, without the platform's ability server.
