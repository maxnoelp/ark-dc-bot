# bot/utils/message_store.py
import json
from pathlib import Path
from typing import Dict, List

FILE = Path("sent_messages.json")


def _read() -> Dict[str, List[int]]:
    if FILE.exists():
        print("Reading sent messages from file", FILE)
        return json.loads(FILE.read_text())
    return {}


def _write(data: Dict[str, List[int]]):
    FILE.write_text(json.dumps(data, indent=2))


def add(guild_id: int, msg_id: int):
    data = _read()
    data.setdefault(str(guild_id), []).append(msg_id)
    _write(data)


def get_all(guild_id: int) -> List[int]:
    return _read().get(str(guild_id), [])


def remove(guild_id: int, msg_id: int):
    data = _read()
    msgs = data.get(str(guild_id), [])
    if msg_id in msgs:
        msgs.remove(msg_id)
        _write(data)


# ---------------------
# ---------- Tickets ----------
def add_ticket(guild_id: int, channel_id: int, first_msg_id: int):
    data = _read()
    key = str(guild_id)
    node = data.get(key)

    # Migration: falls alt (Liste) -> in Dict überführen
    if node is None:
        node = {}
        data[key] = node
    elif isinstance(node, list):
        node = {"legacy": node}  # alte IDs sichern
        data[key] = node
    elif not isinstance(node, dict):
        # Irgendwas Unerwartetes -> überschreiben (oder sichern)
        node = {"_raw": str(node)}
        data[key] = node

    tickets = node.setdefault("tickets", {})
    tickets[str(channel_id)] = first_msg_id
    _write(data)


def get_tickets(guild_id: int) -> Dict[int, int]:
    raw = _read().get(str(guild_id), {}).get("tickets", {})
    # Keys zurück in int konvertieren
    return {int(cid): mid for cid, mid in raw.items()}


def remove_ticket(guild_id: int, channel_id: int):
    data = _read()
    tickets = data.get(str(guild_id), {}).get("tickets", {})
    if str(channel_id) in tickets:
        del tickets[str(channel_id)]
        _write(data)
