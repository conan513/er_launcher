import asyncio
import json
import websockets
import logging
import time
import os
import hashlib

logging.basicConfig(level=logging.INFO)

CLIENTS = {} # websocket: {"nickname": "Unknown", "modpack": "Vanilla", "color": "#gray"}
CHAT_HISTORY = []
MAX_HISTORY = 100
LOG_FILE = "chat_log.json"
MAX_MESSAGE_LENGTH = 500
RATE_LIMIT_SECONDS = 3
IP_LAST_MESSAGE_TIME = {}
NICKNAME_COLOR_MAP = {}
PLAYTIME_FILE = "playtime.json"
PLAYTIME_DATA = {} # user_id: total_seconds
COLOR_PALETTE = [
    "#ff6b6b", "#4ecdc4", "#45b7d1", "#f7d794", "#786fa6", 
    "#f8a5c2", "#63cdda", "#ea8685", "#546de5", "#e15f41",
    "#c44569", "#574b90", "#f5cd79", "#cf6a87", "#3dc1d3",
    "#ff9f43", "#ee5253", "#10ac84", "#0abde3", "#5f27cd",
    "#54a0ff", "#00d2d3", "#ff9ff3", "#feca57", "#48dbfb", 
    "#1dd1a1", "#2ecc71", "#3498db", "#9b59b6", "#e67e22",
    "#e74c3c", "#1abc9c", "#2c3e50", "#f1c40f", "#8e44ad",
    "#2980b9", "#d35400", "#c0392b", "#16a085", "#7f8c8d",
    "#D980FA", "#9980FA", "#833471", "#0652DD", "#1289A7",
    "#EA2027", "#009432", "#F79F1F", "#1B1464", "#5758BB",
    "#6F1E51", "#B53471", "#EE5A24", "#006266", "#1e3799",
    "#b33939", "#218c74", "#33d9b2", "#cd6133", "#40407a",
    "#706fd3", "#f7f1e3", "#34ace0", "#ff5252", "#ff793f",
    "#d1ccc0", "#ffb142", "#ffda79", "#cc8e35", "#ccae62"
]

import random

def get_nickname_color(nickname):
    if nickname not in NICKNAME_COLOR_MAP:
        # Try to find a color that isn't currently used
        used_colors = set(NICKNAME_COLOR_MAP.values())
        available_colors = [c for c in COLOR_PALETTE if c not in used_colors]
        
        if available_colors:
            NICKNAME_COLOR_MAP[nickname] = random.choice(available_colors)
        else:
            # Fallback to random if all palette colors are used
            NICKNAME_COLOR_MAP[nickname] = random.choice(COLOR_PALETTE)
            
    return NICKNAME_COLOR_MAP[nickname]

def save_chat_history():
    try:
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(CHAT_HISTORY, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Failed to save chat history: {e}")

def load_chat_history():
    global CHAT_HISTORY
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                CHAT_HISTORY = json.load(f)
                # Keep only last 100
                if len(CHAT_HISTORY) > MAX_HISTORY:
                    CHAT_HISTORY = CHAT_HISTORY[-MAX_HISTORY:]
            logging.info(f"Loaded {len(CHAT_HISTORY)} messages from history.")
        except Exception as e:
            logging.error(f"Failed to load chat history: {e}")

def save_playtime():
    try:
        temp_file = PLAYTIME_FILE + ".tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(PLAYTIME_DATA, f, ensure_ascii=False, indent=2)
        os.replace(temp_file, PLAYTIME_FILE)
    except Exception as e:
        logging.error(f"Failed to save playtime: {e}")

def load_playtime():
    global PLAYTIME_DATA
    if os.path.exists(PLAYTIME_FILE):
        try:
            with open(PLAYTIME_FILE, "r", encoding="utf-8") as f:
                PLAYTIME_DATA = json.load(f)
            logging.info(f"Loaded playtime data for {len(PLAYTIME_DATA)} users.")
        except Exception as e:
            logging.error(f"Failed to load playtime: {e}")

async def broadcast(message):
    if CLIENTS:
        await asyncio.gather(*(client.send(message) for client in CLIENTS.keys()), return_exceptions=True)

async def broadcast_player_list():
    players = []
    for meta in CLIENTS.values():
        uid = meta.get("user_id", "anonymous")
        total_seconds = PLAYTIME_DATA.get(uid, 0)
        
        # Format playtime string
        if total_seconds < 60:
            playtime_str = f"{int(total_seconds)}s"
        elif total_seconds < 3600:
            playtime_str = f"{int(total_seconds // 60)}m"
        else:
            playtime_str = f"{total_seconds / 3600:.1f}h"

        players.append({
            "nickname": meta["nickname"],
            "modpack": meta["modpack"],
            "in_game": meta.get("in_game", False),
            "game_mode": meta.get("game_mode", "Online"),
            "color": meta["color"],
            "tripcode": meta.get("tripcode", ""),
            "playtime": playtime_str
        })
    await broadcast(json.dumps({"type": "player_list", "players": players}, ensure_ascii=False))

async def handle_client(websocket, path=None):
    ip = websocket.remote_address[0]
    logging.info(f"New client connected: {ip}")
    CLIENTS[websocket] = {
        "nickname": "Unknown", 
        "modpack": "Vanilla", 
        "in_game": False, 
        "game_mode": "Online", 
        "color": "gray"
    }
    
    # Broadcast new user count and list
    await broadcast(json.dumps({"type": "user_count", "count": len(CLIENTS)}, ensure_ascii=False))
    await broadcast_player_list()
    
    # Send history to new client
    if CHAT_HISTORY:
        history_payload = json.dumps({"type": "history", "messages": CHAT_HISTORY}, ensure_ascii=False)
        await websocket.send(history_payload)
        
    first_message = True
    
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                
                if data.get("type") == "status_update":
                    nick = data.get("nickname", "Unknown")
                    mod = data.get("modpack", "Vanilla")
                    in_game = data.get("in_game", False)
                    game_mode = data.get("game_mode", "Online")
                    user_id = data.get("user_id", "anonymous")
                    
                    # Playtime logic: calculate delta if they WERE in game
                    now = time.time()
                    old_meta = CLIENTS[websocket]
                    if old_meta.get("in_game") and "last_status_time" in old_meta:
                        delta = now - old_meta["last_status_time"]
                        uid = old_meta.get("user_id", "anonymous")
                        if uid != "anonymous":
                             PLAYTIME_DATA[uid] = PLAYTIME_DATA.get(uid, 0) + delta
                             save_playtime()

                    tripcode = hashlib.sha256(user_id.encode()).hexdigest()[:4]
                    color = get_nickname_color(nick)
                    CLIENTS[websocket] = {
                        "nickname": nick, 
                        "modpack": mod, 
                        "in_game": in_game, 
                        "game_mode": game_mode, 
                        "color": color,
                        "tripcode": tripcode,
                        "user_id": user_id,
                        "last_status_time": now
                    }
                    await broadcast_player_list()

                elif data.get("type") == "chat":
                    msg_text = data.get("message", "")
                    nick = data.get("nickname", "Unknown")
                    
                    if first_message:
                        first_message = False
                    
                    # 1. Length Limit
                    if len(msg_text) > MAX_MESSAGE_LENGTH:
                        msg_text = msg_text[:MAX_MESSAGE_LENGTH]
                    
                    # 2. Rate Limiting
                    now = time.time()
                    last_time = IP_LAST_MESSAGE_TIME.get(ip, 0)
                    if now - last_time < RATE_LIMIT_SECONDS:
                        continue # Ignore spam
                    
                    IP_LAST_MESSAGE_TIME[ip] = now
                    
                    # Refresh metadata on every message to ensure player list is accurate
                    color = get_nickname_color(nick)
                    user_id = data.get("user_id", "anonymous")
                    tripcode = hashlib.sha256(user_id.encode()).hexdigest()[:4]
                    
                    # Update metadata but KEEP tracking info
                    now = time.time()
                    old_meta = CLIENTS[websocket]
                    # Update playtime on chat as well
                    if old_meta.get("in_game") and "last_status_time" in old_meta:
                        delta = now - old_meta["last_status_time"]
                        uid = old_meta.get("user_id", "anonymous")
                        if uid != "anonymous":
                             PLAYTIME_DATA[uid] = PLAYTIME_DATA.get(uid, 0) + delta
                             save_playtime()

                    CLIENTS[websocket] = {
                        "nickname": nick, 
                        "modpack": data.get("modpack", old_meta["modpack"]), 
                        "in_game": data.get("in_game", old_meta["in_game"]), 
                        "game_mode": data.get("game_mode", old_meta["game_mode"]), 
                        "color": color,
                        "tripcode": tripcode,
                        "user_id": user_id,
                        "last_status_time": now
                    }
                    
                    # Generate Tripcode if user_id is provided
                    tripcode = hashlib.sha256(user_id.encode()).hexdigest()[:4]
                    
                    # Store in history
                    chat_entry = {
                        "nickname": nick, 
                        "message": msg_text, 
                        "time": time.strftime("%H:%M"),
                        "color": color,
                        "tripcode": tripcode
                    }
                    CHAT_HISTORY.append(chat_entry)
                    if len(CHAT_HISTORY) > MAX_HISTORY:
                        CHAT_HISTORY.pop(0)
                    
                    # Persistent Save
                    save_chat_history()
                        
                    # Broadcast to all
                    await broadcast(json.dumps({"type": "chat", **chat_entry}, ensure_ascii=False))

                elif data.get("type") == "request_history":
                    # Send history to the requester only
                    if CHAT_HISTORY:
                        history_payload = json.dumps({"type": "history", "messages": CHAT_HISTORY}, ensure_ascii=False)
                        await websocket.send(history_payload)
                    
                elif data.get("type") == "request_player_list":
                    # Send player list to the requester only
                    players = []
                    for meta in CLIENTS.values():
                        uid = meta.get("user_id", "anonymous")
                        total_seconds = PLAYTIME_DATA.get(uid, 0)
                        
                        if total_seconds < 60: playtime_str = f"{int(total_seconds)}s"
                        elif total_seconds < 3600: playtime_str = f"{int(total_seconds // 60)}m"
                        else: playtime_str = f"{total_seconds / 3600:.1f}h"

                        players.append({
                            "nickname": meta["nickname"],
                            "modpack": meta["modpack"],
                            "in_game": meta.get("in_game", False),
                            "game_mode": meta.get("game_mode", "Online"),
                            "color": meta["color"],
                            "tripcode": meta.get("tripcode", ""),
                            "playtime": playtime_str
                        })
                    await websocket.send(json.dumps({"type": "player_list", "players": players}, ensure_ascii=False))

            except json.JSONDecodeError:
                logging.warning(f"Invalid JSON received from {ip}")
    except websockets.exceptions.ConnectionClosed:
        logging.info(f"Client disconnected: {ip}")
    finally:
        if websocket in CLIENTS:
            meta = CLIENTS[websocket]
            # Final playtime capture on disconnect
            if meta.get("in_game") and "last_status_time" in meta:
                now = time.time()
                delta = now - meta["last_status_time"]
                uid = meta.get("user_id", "anonymous")
                if uid != "anonymous":
                    PLAYTIME_DATA[uid] = PLAYTIME_DATA.get(uid, 0) + delta
                    save_playtime()
            del CLIENTS[websocket]
            
        # Broadcast updated user count and list
        await broadcast(json.dumps({"type": "user_count", "count": len(CLIENTS)}, ensure_ascii=False))
        await broadcast_player_list()

# Load history on module load
load_chat_history()
load_playtime()

async def main():
    # Use 0.0.0.0 to allow external connections, port 8765
    try:
        async with websockets.serve(handle_client, "0.0.0.0", 8765):
            logging.info("WebSocket server started on ws://0.0.0.0:8765")
            await asyncio.Future()  # run forever
    except Exception as e:
        logging.error(f"Fatal server error: {e}")
        raise e

if __name__ == "__main__":
    while True:
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            logging.info("Server stopped by user.")
            break
        except Exception as e:
            if "10048" in str(e) or "Address already in use" in str(e):
                logging.error(f"Port 8765 is already in use. Retrying in 10s... {e}")
                time.sleep(10)
            else:
                logging.error(f"Server crashed, restarting in 2s: {e}")
                time.sleep(2)
