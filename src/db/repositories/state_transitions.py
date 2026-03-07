from sqlalchemy.orm import Session

from src.db.models.core import StateTransitionLog


class StateTransitionsRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(
        self,
        *,
        entity_type: str,
        entity_id,
        from_state,
        to_state: str,
        trigger_type: str,
        trigger_ref_id=None,
        actor_user_id=None,
        metadata_json=None,
    ) -> StateTransitionLog:
        row = StateTransitionLog(
            entity_type=entity_type,
            entity_id=entity_id,
            from_state=from_state,
            to_state=to_state,
            trigger_type=trigger_type,
            trigger_ref_id=trigger_ref_id,
            actor_user_id=actor_user_id,
            metadata_json=metadata_json,
        )
        self.session.add(row)
        self.session.flush()
        return row

