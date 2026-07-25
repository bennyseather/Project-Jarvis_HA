# M13 Home Assistant Conversation Integration

On Home Assistant OS, Jarvis is deployed as an add-on and reached from Assist
through a custom conversation integration. The integration forwards text to an
authenticated local Jarvis bridge; it does not control Home Assistant directly.

Confirmation tokens remain one-time and are consumed by Jarvis, not by the
integration. The add-on uses Home Assistant's internal proxy and add-on storage;
it does not require host networking or a long-lived Home Assistant token.

The repository includes initial add-on and custom-component packaging artifacts.
Installing them into Home Assistant OS is a separate deployment action and is
not performed from this workspace.
