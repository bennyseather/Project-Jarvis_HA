# M17 Home Understanding

Jarvis reads Home Assistant's entity and area registries at startup. It resolves configured aliases, friendly names, exact area names, and Home Assistant group names deterministically. An ambiguous friendly name requires clarification; an area or group can expand only to its currently authorized members. Metadata is bounded in model context and no state history or conversation text is retained.
