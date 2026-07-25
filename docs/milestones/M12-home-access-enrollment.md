# M12 Home Assistant Access Enrollment

M12 separates discovery from permission. `home discover [domain]` shows up to
100 currently discovered entity IDs and services; it grants nothing.

Explicit enrollment commands persist only to `config/general.yaml` and require
a Jarvis restart before they apply:

- `home enroll read <entity-id>`
- `home enroll action <entity-id> <domain.service> [normal|high]`
- `home alias <friendly-name> <enrolled-entity-id>`

High-impact domains—locks, alarms, covers, garage doors, scripts, and
automations—must be enrolled with `high` risk. All enrolled actions still use
the existing one-time confirmation gateway. The workflow never edits
`secrets.yaml`, never enrolls discovered items automatically, and never lets
the language model alter access configuration.

## Completed acceptance run

On 2026-07-26, read-only Home Assistant discovery found six cover entities and
ten cover services. The check did not enroll an entity, modify configuration,
or call a Home Assistant service.
