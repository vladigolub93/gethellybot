from sqlalchemy.orm import Session

from src.db.repositories.state_transitions import StateTransitionsRepository


class StateService:
    def __init__(self, session: Session):
        self.session = session
        self.transitions = StateTransitionsRepository(session)

    def record_transition(
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
    ) -> None:
        self.transitions.create(
            entity_type=entity_type,
            entity_id=entity_id,
            from_state=from_state,
            to_state=to_state,
            trigger_type=trigger_type,
            trigger_ref_id=trigger_ref_id,
            actor_user_id=actor_user_id,
            metadata_json=metadata_json,
        )

    def transition(
        self,
        *,
        entity_type: str,
        entity,
        to_state: str,
        trigger_type: str,
        trigger_ref_id=None,
        actor_user_id=None,
        metadata_json=None,
        state_field: str = "state",
    ) -> None:
        from_state = getattr(entity, state_field, None)
        setattr(entity, state_field, to_state)
        self.session.flush()
        self.record_transition(
            entity_type=entity_type,
            entity_id=entity.id,
            from_state=from_state,
            to_state=to_state,
            trigger_type=trigger_type,
            trigger_ref_id=trigger_ref_id,
            actor_user_id=actor_user_id,
            metadata_json=metadata_json,
        )
