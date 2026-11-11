"""Avisos do contrato (W1..W4): registram no log e no relatorio, nunca bloqueiam.

Cada aviso so e avaliado se as colunas de que depende existirem; um lote malformado ja
e reprovado pelas regras criticas e nao deve derrubar a validacao aqui.
"""

from typing import Any

import pandas as pd

from src.contracts.result import Violation
from src.data.schema import BILL_COLUMNS, ID_COLUMN

LATE_PAYMENT_COLUMN = "PAY_0"
LATE_PAYMENT_STATUS = 2  # dois ou mais meses de atraso


def soft_checks(
    frame: pd.DataFrame,
    config: dict[str, Any],
    expected_rows: int | None = None,
    reference: pd.DataFrame | None = None,
) -> list[Violation]:
    """Avalia os avisos do contrato.

    Args:
        frame: Lote a validar.
        config: Secao ``contract.warnings`` da configuracao.
        expected_rows: Volume esperado do lote (W2); ``None`` desliga o aviso.
        reference: Conjunto de referencia (W3); ``None`` desliga o aviso.

    Returns:
        Avisos disparados, em ordem de regra.
    """
    found = [
        _negative_bills(frame, config["bill_amt_min"]),
        _volume(frame, expected_rows, config["volume_tolerance"]),
        _late_payments(frame, reference, config["late_payment_ratio_max"]),
        _identical_profiles(frame),
    ]
    return [warning for warning in found if warning is not None]


def _negative_bills(frame: pd.DataFrame, floor: float) -> Violation | None:
    columns = [name for name in BILL_COLUMNS if name in frame]
    if not columns:
        return None
    below = frame[columns].min(axis=1) < floor
    if not below.any():
        return None
    examples = sorted(frame.loc[below, columns].min(axis=1).astype(int).unique().tolist())[:3]
    return Violation("W1", "BILL_AMT*", f"min < {floor}", int(below.sum()), examples)


def _volume(frame: pd.DataFrame, expected: int | None, tolerance: float) -> Violation | None:
    if expected is None or abs(len(frame) - expected) <= tolerance * expected:
        return None
    return Violation("W2", None, f"rows outside {expected} +-{tolerance:.0%}", len(frame))


def _late_payments(
    frame: pd.DataFrame, reference: pd.DataFrame | None, max_ratio: float
) -> Violation | None:
    if reference is None or LATE_PAYMENT_COLUMN not in frame:
        return None
    batch_rate = float((frame[LATE_PAYMENT_COLUMN] >= LATE_PAYMENT_STATUS).mean())
    reference_rate = float((reference[LATE_PAYMENT_COLUMN] >= LATE_PAYMENT_STATUS).mean())
    if batch_rate <= max_ratio * reference_rate:
        return None
    check = f"share(PAY_0 >= 2) > {max_ratio}x reference"
    late = int((frame[LATE_PAYMENT_COLUMN] >= LATE_PAYMENT_STATUS).sum())
    return Violation(
        "W3", LATE_PAYMENT_COLUMN, check, late, [round(batch_rate, 4), round(reference_rate, 4)]
    )


def _identical_profiles(frame: pd.DataFrame) -> Violation | None:
    if ID_COLUMN not in frame:
        return None
    copies = int(frame.drop(columns=ID_COLUMN).duplicated(keep="first").sum())
    if copies == 0:
        return None
    return Violation("W4", None, "identical rows under different IDs", copies)
