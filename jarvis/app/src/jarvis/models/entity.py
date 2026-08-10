"""
Represents a Home Assistant entity.
"""


class Entity:
    """
    Represents a single Home Assistant entity.
    """

    def __init__(self, data: dict):
        self.entity_id = data["entity_id"]
        self.state = data["state"]

        self.attributes = data.get("attributes", {})

        self.friendly_name = self.attributes.get(
            "friendly_name",
            self.entity_id,
        )

        self.domain = self.entity_id.split(".", 1)[0]

    def __repr__(self):
        return (
            f"Entity("
            f"entity_id='{self.entity_id}', "
            f"state='{self.state}')"
        )