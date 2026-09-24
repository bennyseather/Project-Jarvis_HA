"""Server-side identity mapping. Not a wire-authentication implementation.

Only a trusted adapter may supply an independently verified account ID and
session mode. Never construct them from conversation payload/source_id claims.
This module is not connected to the legacy shared-key HTTP bridge.
"""
from dataclasses import dataclass
import hashlib
import json


@dataclass(frozen=True)
class HouseholdSubject:
    member_id: str | None = None

    def conversation_key(self, session_id):
        if not isinstance(session_id, str) or not session_id or len(session_id) > 512:
            raise ValueError('A bounded server-owned session ID is required')
        encoded = json.dumps([self.member_id, session_id], separators=(',', ':'))
        return 'household:' + hashlib.sha256(encoded.encode()).hexdigest()


class HouseholdAccess:
    def __init__(self, known_members, private_accounts, *, shared_accounts=()):
        self._members = frozenset(known_members)
        self._accounts = dict(private_accounts)
        self._shared = frozenset(shared_accounts)
        if self._shared.intersection(self._accounts):
            raise ValueError('Shared accounts cannot be mapped to a private member')
        for account, member in self._accounts.items():
            if not isinstance(account, str) or not account.strip() or member not in self._members:
                raise ValueError('Account mappings must reference known members')

    def resolve(self, *, verified_account_id=None, private_session=False, voice=False):
        # Even an authenticated kiosk account is not proof of the speaker.
        if private_session is not True or voice is not False or verified_account_id in self._shared:
            return HouseholdSubject()
        return HouseholdSubject(self._accounts.get(verified_account_id))
