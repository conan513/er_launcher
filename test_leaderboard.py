import json

# Simulate the server's leaderboard response
USER_DATA = {
    "99d04503-41b3-4d52-9ce7-bc447804e722": {
        "playtime": 2108.2949228286743,
        "nickname": "Conan",
        "tripcode": "7c98"
    }
}

print("=== SIMULATING LEADERBOARD REQUEST ===")
print(f"USER_DATA has {len(USER_DATA)} entries.")

# Sort by playtime descending
leaderboard_candidates = []
for uid, info in USER_DATA.items():
    # Robust check: info MUST be a dict
    if isinstance(info, dict) and info.get("playtime", 0) >= 0:
        leaderboard_candidates.append((uid, info.get("playtime", 0)))

print(f"Found {len(leaderboard_candidates)} valid leaderboard candidates.")

sorted_playtime = sorted(leaderboard_candidates, key=lambda x: x[1], reverse=True)[:50]
leaderboard = []

for uid, total_seconds in sorted_playtime:
    info = USER_DATA.get(uid, {})
    if not isinstance(info, dict): 
        info = {}
    
    if total_seconds < 60: 
        playtime_str = f"{int(total_seconds)}s"
    elif total_seconds < 3600: 
        playtime_str = f"{int(total_seconds // 60)}m"
    else: 
        playtime_str = f"{total_seconds / 3600:.1f}h"
    
    leaderboard.append({
        "nickname": info.get("nickname", "Anonymous"),
        "tripcode": info.get("tripcode", "????"),
        "playtime": playtime_str,
        "playtime_seconds": total_seconds
    })

print(f"Sending leaderboard with {len(leaderboard)} entries.")
print("\n=== LEADERBOARD DATA ===")
print(json.dumps({"type": "leaderboard", "entries": leaderboard}, indent=2, ensure_ascii=False))
