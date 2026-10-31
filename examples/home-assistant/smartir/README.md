# SmartIR profile for a Domo mobile A/C (custom)

No Domo profile exists in SmartIR, so this is a minimal one built from codes
learned with a Broadlink RM Mini: cool mode, auto fan, 22-26 °C + off.

1. Learn the codes (Developer tools > Actions), one per remote state:

   ```yaml
   action: remote.learn_command
   target:
     entity_id: remote.rm_mini
   data:
     device: clim_domo
     command: [off, cool_22, cool_23, cool_24, cool_25, cool_26]
   ```

   Before each press, set the physical remote to that exact state
   (cool, auto fan, temperature), because A/C remotes send their full state.

2. Read the learned codes:

   ```bash
   jq '.data.clim_domo' /config/.storage/broadlink_remote_*_codes
   ```

   Paste each one in `9001.json` (remove a leading `b64:` if present).

3. Copy `9001.json` to `/config/custom_components/smartir/codes/climate/`
   (keep a backup: updating SmartIR may replace that folder).

4. Add the climate entity, see `climate.yaml`.
