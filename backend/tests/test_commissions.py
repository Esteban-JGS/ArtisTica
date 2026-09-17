import pytest
from src.models.commissions import CommissionState, COMMISSION_TRANSITIONS
from src.core.exceptions import InvalidStateTransition

def safe_transition(current: CommissionState, target: CommissionState):
    """Lógica pura de transición para validar la máquina de estados."""
    allowed_transitions = COMMISSION_TRANSITIONS.get(current, [])
    if target not in allowed_transitions:
        raise InvalidStateTransition(f"No se permite transicionar de {current} a {target}")
    return target

def test_valid_commission_transition():
    """Verifica que la máquina permite una transición válida de la vida real."""
    new_state = safe_transition(CommissionState.SOLICITADA, CommissionState.COTIZADA)
    assert new_state == CommissionState.COTIZADA

def test_invalid_commission_transition_raises_error():
    """Verifica que intentar saltarse un estado levanta la excepción del dominio."""
    with pytest.raises(InvalidStateTransition):
        # Tratar de entregar sin que haya sido aceptada ni pagada en retencion
        safe_transition(CommissionState.SOLICITADA, CommissionState.ENTREGADA)
