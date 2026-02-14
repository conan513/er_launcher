import asyncio
import json
import websockets
import logging
import time
import os
import hashlib

SERVER_BASE = os.path.dirname(os.path.abspath(__file__))
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(SERVER_BASE, "server.log"), encoding='utf-8'),
        logging.StreamHandler()
    ]
)

CLIENTS = {} # websocket: {"nickname": "Unknown", "modpack": "Vanilla", "color": "#gray"}
CHAT_HISTORY = []
MAX_HISTORY = 100
LOBBIES = {} # websocket: {"password": "...", "nickname": "...", "color": "..."}
MAX_MESSAGE_LENGTH = 500
RATE_LIMIT_SECONDS = 3
IP_LAST_MESSAGE_TIME = {}
NICKNAME_COLOR_MAP = {}
LOG_FILE = os.path.join(SERVER_BASE, "chat_log.json")
USER_DATA_FILE = os.path.join(SERVER_BASE, "user_data.json")
USER_DATA = {} # user_id: {"nickname": "...", "tripcode": "...", "playtime": 0}
# Old files for migration
PLAYTIME_FILE = os.path.join(SERVER_BASE, "playtime.json")
USER_METADATA_FILE = os.path.join(SERVER_BASE, "user_metadata.json")
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

def save_user_data():
    try:
        temp_file = USER_DATA_FILE + ".tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(USER_DATA, f, ensure_ascii=False, indent=2)
        os.replace(temp_file, USER_DATA_FILE)
    except Exception as e:
        logging.error(f"Failed to save user data: {e}")

def load_user_data():
    global USER_DATA
    logging.info(f"Loading user data from: {USER_DATA_FILE}")
    # 1. Load existing user_data.json if it exists
    if os.path.exists(USER_DATA_FILE):
        try:
            with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
                USER_DATA = json.load(f)
            logging.info(f"Loaded unified data for {len(USER_DATA)} users.")
        except Exception as e:
            logging.error(f"Failed to load user data: {e}")
            
    # 2. Migration Logic: If user_data is empty or new, check for old separate files
    migrated = False
    if os.path.exists(PLAYTIME_FILE):
        try:
            with open(PLAYTIME_FILE, "r", encoding="utf-8") as f:
                old_playtime = json.load(f)
                for uid, seconds in old_playtime.items():
                    if uid not in USER_DATA: USER_DATA[uid] = {}
                    USER_DATA[uid]["playtime"] = USER_DATA[uid].get("playtime", 0) + seconds
            logging.info("Migrated old playtime data.")
            migrated = True
        except Exception as e:
            logging.error(f"Migration error (playtime): {e}")

    if os.path.exists(USER_METADATA_FILE):
        try:
            with open(USER_METADATA_FILE, "r", encoding="utf-8") as f:
                old_meta = json.load(f)
                for uid, meta in old_meta.items():
                    if uid not in USER_DATA: USER_DATA[uid] = {}
                    USER_DATA[uid]["nickname"] = meta.get("nickname", "Anonymous")
                    USER_DATA[uid]["tripcode"] = meta.get("tripcode", "????")
            logging.info("Migrated old metadata.")
            migrated = True
        except Exception as e:
            logging.error(f"Migration error (metadata): {e}")
            
    if migrated:
        save_user_data()
        logging.info(f"Consolidated data saved to {USER_DATA_FILE}. Migration successful.")
    else:
        logging.info("No migration files found or migration not needed.")

async def broadcast(message):
    if CLIENTS:
        await asyncio.gather(*(client.send(message) for client in CLIENTS.keys()), return_exceptions=True)

async def broadcast_player_list():
    players = []
    for meta in CLIENTS.values():
        uid = meta.get("user_id", "anonymous")
        user_info = USER_DATA.get(uid, {})
        total_seconds = user_info.get("playtime", 0)
        
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

async def broadcast_lobby_list():
    lobbies = []
    for meta in LOBBIES.values():
        lobbies.append({
            "nickname": meta["nickname"],
            "password": meta["password"],
            "color": meta["color"]
        })
    await broadcast(json.dumps({"type": "lobby_list", "lobbies": lobbies}, ensure_ascii=False))

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
        
    # Send lobby list to new client
    await broadcast_lobby_list()
        
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
                            if uid not in USER_DATA: USER_DATA[uid] = {}
                            USER_DATA[uid]["playtime"] = USER_DATA[uid].get("playtime", 0) + delta
                            logging.info(f"[PLAYTIME] User {nick} ({uid[:8]}): +{delta:.1f}s (was in_game, now: {in_game})")
                            save_user_data()
                    else:
                        logging.debug(f"[PLAYTIME] User {nick}: No time added (in_game: {old_meta.get('in_game', False)} -> {in_game})")

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
                    
                    # Update metadata
                    if user_id != "anonymous":
                        if user_id not in USER_DATA: USER_DATA[user_id] = {}
                        USER_DATA[user_id].update({
                            "nickname": nick,
                            "tripcode": tripcode
                        })
                        save_user_data()
                    
                    # Auto-remove lobby if player is no longer in-game
                    if not in_game and websocket in LOBBIES:
                        logging.info(f"Removing lobby for {nick} - game exited.")
                        del LOBBIES[websocket]
                        await broadcast_lobby_list()

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
                            if uid not in USER_DATA: USER_DATA[uid] = {}
                            USER_DATA[uid]["playtime"] = USER_DATA[uid].get("playtime", 0) + delta
                            save_user_data()

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
                        user_info = USER_DATA.get(uid, {})
                        total_seconds = user_info.get("playtime", 0)
                        
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
                
                elif data.get("type") == "host_lobby":
                    password = data.get("password", "")
                    if password:
                        meta = CLIENTS.get(websocket, {})
                        LOBBIES[websocket] = {
                            "password": password,
                            "nickname": meta.get("nickname", "Unknown"),
                            "color": meta.get("color", "gray")
                        }
                        logging.info(f"Lobby hosted by {LOBBIES[websocket]['nickname']} with pass: {password}")
                        await broadcast_lobby_list()

                elif data.get("type") == "request_lobbies":
                    await broadcast_lobby_list()

                elif data.get("type") == "request_leaderboard":
                    logging.info(f"Leaderboard requested. USER_DATA has {len(USER_DATA)} entries.")
                    # Sort by playtime descending
                    leaderboard_candidates = []
                    for uid, info in USER_DATA.items():
                        # Robust check: info MUST be a dict
                        if isinstance(info, dict) and info.get("playtime", 0) >= 0:
                            leaderboard_candidates.append((uid, info.get("playtime", 0)))
                    
                    logging.info(f"Found {len(leaderboard_candidates)} valid leaderboard candidates.")
                    sorted_playtime = sorted(leaderboard_candidates, key=lambda x: x[1], reverse=True)[:50]
                    leaderboard = []
                    for uid, total_seconds in sorted_playtime:
                        info = USER_DATA.get(uid, {})
                        if not isinstance(info, dict): info = {}
                        
                        if total_seconds < 60: playtime_str = f"{int(total_seconds)}s"
                        elif total_seconds < 3600: playtime_str = f"{int(total_seconds // 60)}m"
                        else: playtime_str = f"{total_seconds / 3600:.1f}h"
                        
                        leaderboard.append({
                            "nickname": info.get("nickname", "Anonymous"),
                            "tripcode": info.get("tripcode", "????"),
                            "playtime": playtime_str,
                            "playtime_seconds": total_seconds
                        })
                    logging.info(f"Sending leaderboard with {len(leaderboard)} entries.")
                    await websocket.send(json.dumps({"type": "leaderboard", "entries": leaderboard}, ensure_ascii=False))

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
                    if uid not in USER_DATA: USER_DATA[uid] = {}
                    USER_DATA[uid]["playtime"] = USER_DATA[uid].get("playtime", 0) + delta
                    save_user_data()
            del CLIENTS[websocket]
            
        if websocket in LOBBIES:
            del LOBBIES[websocket]
            await broadcast_lobby_list()
            
        # Broadcast updated user count and list
        await broadcast(json.dumps({"type": "user_count", "count": len(CLIENTS)}, ensure_ascii=False))
        await broadcast_player_list()

# Load data on module load
load_chat_history()
load_user_data()

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
