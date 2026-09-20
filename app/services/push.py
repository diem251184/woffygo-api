"""Servicio de envio de notificaciones push via Expo Push API.

Expo Push API:
- Endpoint: https://exp.host/--/api/v2/push/send
- Acepta hasta 100 mensajes por request.
- Si un token es invalido, devuelve error y lo desactivamos.
"""
import httpx
from sqlalchemy.orm import Session

from app.models.device_token import DeviceToken


EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


def _get_tokens_for_user(db: Session, user_id: int) -> list[str]:
    """Devuelve los tokens activos de un usuario."""
    rows = (
        db.query(DeviceToken.token)
        .filter(DeviceToken.user_id == user_id)
        .filter(DeviceToken.is_active.is_(True))
        .all()
    )
    return [r[0] for r in rows]


def _get_tokens_for_users(db: Session, user_ids: list[int]) -> dict[int, list[str]]:
    """Devuelve un dict {user_id: [tokens]} para varios usuarios."""
    if not user_ids:
        return {}
    rows = (
        db.query(DeviceToken.user_id, DeviceToken.token)
        .filter(DeviceToken.user_id.in_(user_ids))
        .filter(DeviceToken.is_active.is_(True))
        .all()
    )
    result: dict[int, list[str]] = {}
    for user_id, token in rows:
        result.setdefault(user_id, []).append(token)
    return result


def _deactivate_tokens(db: Session, tokens: list[str]) -> None:
    """Marca tokens como inactivos (para los que Expo reporta error)."""
    if not tokens:
        return
    db.query(DeviceToken).filter(DeviceToken.token.in_(tokens)).update(
        {DeviceToken.is_active: False}, synchronize_session=False
    )
    db.commit()


def _send_batch(messages: list[dict]) -> list[dict]:
    """Envia hasta 100 mensajes a Expo Push API. Devuelve la lista de resultados."""
    if not messages:
        return []
    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.post(
                EXPO_PUSH_URL,
                json=messages,
                headers={
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip, deflate",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            data = response.json()
            if isinstance(data, dict) and "data" in data:
                return data["data"]
            return data if isinstance(data, list) else []
    except Exception as e:
        print(f"[push] Error enviando a Expo: {e}")
        return []


def _build_message(token: str, title: str, body: str, data: dict | None = None) -> dict:
    msg = {
        "to": token,
        "title": title,
        "body": body,
        "sound": "default",
        "priority": "high",
        "channelId": "walks",
    }
    if data:
        msg["data"] = data
    return msg


def send_to_user(
    db: Session,
    user_id: int,
    title: str,
    body: str,
    data: dict | None = None,
) -> int:
    """Envia una push a todas las devices activas de un usuario. Devuelve cuantos envios intento."""
    tokens = _get_tokens_for_user(db, user_id)
    if not tokens:
        return 0
    messages = [_build_message(t, title, body, data) for t in tokens]
    results = _send_batch(messages)
    _handle_results(db, tokens, results)
    return len(tokens)


def send_to_users(
    db: Session,
    user_ids: list[int],
    title: str,
    body: str,
    data: dict | None = None,
) -> int:
    """Envia push a multiples usuarios. Devuelve cuantos envios intento."""
    if not user_ids:
        return 0
    user_tokens = _get_tokens_for_users(db, user_ids)
    all_tokens: list[str] = []
    all_messages: list[dict] = []
    for uid, tokens in user_tokens.items():
        for t in tokens:
            all_tokens.append(t)
            all_messages.append(_build_message(t, title, body, data))
    if not all_messages:
        return 0
    # Enviar en batches de 100
    total_sent = 0
    for i in range(0, len(all_messages), 100):
        chunk_msgs = all_messages[i:i+100]
        chunk_tokens = all_tokens[i:i+100]
        results = _send_batch(chunk_msgs)
        _handle_results(db, chunk_tokens, results)
        total_sent += len(chunk_msgs)
    return total_sent


def _handle_results(db: Session, tokens: list[str], results: list[dict]) -> None:
    """Desactiva tokens que Expo reporta como invalidos."""
    invalid_tokens: list[str] = []
    for token, result in zip(tokens, results):
        if not isinstance(result, dict):
            continue
        status = result.get("status")
        if status == "error":
            details = result.get("details") or {}
            error_code = details.get("error")
            if error_code in ("DeviceNotRegistered", "InvalidCredentials"):
                invalid_tokens.append(token)
    if invalid_tokens:
        _deactivate_tokens(db, invalid_tokens)
