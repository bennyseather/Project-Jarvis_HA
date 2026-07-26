# Project Jarvis add-on

Set an OpenAI API key and a long random bridge API key in the add-on options.
The add-on stores its SQLite database in its persistent add-on configuration
folder. It uses the Home Assistant Supervisor's internal API proxy and does not
need a Home Assistant long-lived token.

Jarvis controls discovered device entities immediately. Home Assistant
administration, backups, add-on management, configuration changes, automations,
and scripts are intentionally unavailable. Use `home exclude <entity_id>` and
restart the add-on to remove a device from Jarvis access.

Install the companion `jarvis_conversation` custom component, then configure
its bridge URL as `http://local-jarvis:8099` for a locally installed add-on and
enter the same bridge API key.
