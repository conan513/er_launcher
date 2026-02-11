import asyncio
import json
import websockets
import logging
import time
import os
import hashlib

logging.basicConfig(level=logging.INFO)

CLIENTS = set()
CHAT_HISTORY = []
MAX_HISTORY = 100
LOG_FILE = "chat_log.json"
MAX_MESSAGE_LENGTH = 500
RATE_LIMIT_SECONDS = 3
IP_LAST_MESSAGE_TIME = {}
NICKNAME_COLOR_MAP = {}
COLOR_PALETTE = [
    "#ff6b6b", "#4ecdc4", "#45b7d1", "#f7d794", "#786fa6", 
    "#f8a5c2", "#63cdda", "#ea8685", "#546de5", "#e15f41",
    "#c44569", "#574b90", "#f5cd79", "#cf6a87", "#3dc1d3",
    "#ff9f43", "#ee5253", "#10ac84", "#0abde3", "#5f27cd",
    "#54a0ff", "#00d2d3", "#ff9ff3", "#feca57", "#ff6b6b",
    "#48dbfb", "#1dd1a1", "#ff9ff3", "#54a0ff", "#5f27cd"
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

async def broadcast(message):
    if CLIENTS:
        await asyncio.gather(*(client.send(message) for client in CLIENTS), return_exceptions=True)

async def handle_client(websocket, path=None):
    ip = websocket.remote_address[0]
    logging.info(f"New client connected: {ip}")
    CLIENTS.add(websocket)
    
    # Broadcast new user count
    await broadcast(json.dumps({"type": "user_count", "count": len(CLIENTS)}, ensure_ascii=False))
    
    # Send history to new client
    if CHAT_HISTORY:
        history_payload = json.dumps({"type": "history", "messages": CHAT_HISTORY}, ensure_ascii=False)
        await websocket.send(history_payload)
        
    first_message = True
    nick = "Unknown"
    
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                if data.get("type") == "chat":
                    msg_text = data.get("message", "")
                    nick = data.get("nickname", "Unknown")
                    
                    if first_message:
                        # Join notification removed as per user request
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
                    
                    # Get color for nickname
                    color = get_nickname_color(nick)
                    
                    # Generate Tripcode if user_id is provided
                    user_id = data.get("user_id", "anonymous")
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
                    
            except json.JSONDecodeError:
                logging.warning(f"Invalid JSON received from {ip}")
    except websockets.exceptions.ConnectionClosed:
        logging.info(f"Client disconnected: {ip}")
    finally:
        CLIENTS.remove(websocket)
        # Leave notification removed as per user request
        pass
            
        # Broadcast updated user count
        await broadcast(json.dumps({"type": "user_count", "count": len(CLIENTS)}, ensure_ascii=False))

# Load history on module load
load_chat_history()

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
