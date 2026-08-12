# Namron 4512751 local ZHA quirk

This narrowly matched quirk fixes Namron `4512751` dimmers that execute on/off
and level commands but omit the Zigbee application response expected by ZHA.
It does not suppress radio delivery errors or affect any other model.

## Home Assistant OS installation

1. Create `/config/custom_zha_quirks` with File editor, Studio Code Server, or
   the Samba share.
2. Copy `namron_4512751.py` into that directory.
3. Add this to `/config/configuration.yaml`, merging it into an existing `zha:`
   section if one exists:

   ```yaml
   zha:
     custom_quirks_path: /config/custom_zha_quirks
   ```

4. Check configuration and restart Home Assistant. Reloading automations is not
   sufficient because quirks are loaded when ZHA starts.
5. Open the dimmer, download diagnostics, and confirm `quirk_applied` is `true`
   and the quirk class references `namron_4512751`.
6. Call `light.turn_on`, `light.turn_off`, and a brightness change. Each action
   should return promptly and the physical light should follow it.

## Rollback

Remove `namron_4512751.py`, remove `custom_quirks_path` if no other local quirks
use it, and restart Home Assistant.
