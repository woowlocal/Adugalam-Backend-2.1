"""
Restore all missing functions from VS Code history backup.
The backup file has the full original views.py from before corruption.
We extract everything after vendor_status_toggle from the backup and append it
to the current views.py (which has everything up to vendor_status_toggle + event views).
"""
import os, json, re

# Paths
history_dir = r"C:\Users\Manicka pream\AppData\Roaming\Code\User\History\-3217f634"
views_path = r"c:\Users\Manicka pream\OneDrive\Desktop\Demo\backend\turf_backend\core\views.py"

# Read backup
entries = json.load(open(os.path.join(history_dir, "entries.json")))
latest_id = entries["entries"][-1]["id"]
backup_text = open(os.path.join(history_dir, latest_id), encoding="utf-8", errors="ignore").read()

# Find the part in backup AFTER vendor_status_toggle function ends
# In backup, after vendor_status_toggle there's update_vendor_by_code, admin_add_turf, etc.
# Find "def update_vendor_by_code" in backup
marker = "def update_vendor_by_code"
idx = backup_text.find(marker)
if idx == -1:
    print("ERROR: Could not find marker in backup!")
    exit(1)

# Go back to find the @api_view decorator before it
chunk_start = backup_text.rfind("@api_view", 0, idx)
backup_chunk = backup_text[chunk_start:]

# Now read current views.py
current_text = open(views_path, "r", encoding="utf-8").read()

# Find where to insert - before "# ==================== EVENTS =="
events_marker = "# ==================== EVENTS =="
events_idx = current_text.find(events_marker)
if events_idx == -1:
    print("ERROR: Could not find EVENTS marker in current file!")
    exit(1)

# Remove the favorite turf functions from backup_chunk since they should be
# at the END of the backup, and we want to insert them before the EVENTS section
# But actually the backup_chunk ends with toggle_favorite and my_favorite_turfs
# which don't have event views. So we append backup_chunk and then the events section.

# Find toggle_favorite + my_favorite_turfs end in backup
fav_end_marker = "my_favorite_turfs"
fav_end_idx = backup_chunk.find("def my_favorite_turfs")
if fav_end_idx != -1:
    # Find the end of my_favorite_turfs function
    lines = backup_chunk.split("\n")
    in_func = False
    end_line = len(lines)
    for i, line in enumerate(lines):
        if "def my_favorite_turfs" in line:
            in_func = True
        elif in_func and line.strip() and not line.startswith(" ") and not line.startswith("\t"):
            end_line = i
            break
    backup_functions = "\n".join(lines[:end_line]) + "\n"
else:
    backup_functions = backup_chunk

# Get the events section from current file
events_section = current_text[events_idx:]

# Build the new file: everything before EVENTS marker + backup functions + events section
new_text = current_text[:events_idx] + backup_functions + "\n\n" + events_section

# Write
with open(views_path, "w", encoding="utf-8") as f:
    f.write(new_text)

# Verify
new_text2 = open(views_path, encoding="utf-8").read()
fns = re.findall(r"def (\w+)\(", new_text2)
print(f"Total lines: {new_text2.count(chr(10)) + 1}")
print(f"Total functions: {len(fns)}")
print(f"Functions: {', '.join(fns)}")

# Check all required functions exist
required = [
    "admin_banner_detail", "admin_manage_banners", "list_homepage_banners",
    "admin_add_turf", "update_turf_priority", "admin_edit_turf",
    "book_slot", "turf_slots", "vendor_set_peak_hour", "vendor_delete_peak_hour",
    "location_list", "select_location", "booking_summary",
    "user_latest_booking", "user_all_bookings", "update_user_profile",
    "submit_contact_message", "list_contact_messages",
    "get_hit_stats", "record_hit", "get_users", "update_user", "delete_user",
    "user_retire_request", "restore_account", "admin_retire_requests", "admin_retire_action",
    "payments_report", "admin_refund_booking", "user_notifications",
    "admin_forgot_password", "admin_reset_password",
    "vendor_profile", "vendor_my_turfs",
    "toggle_favorite", "my_favorite_turfs",
    "list_events", "admin_events", "admin_event_detail", "book_event",
    "event_reviews_list", "admin_event_reviews",
]
missing = [f for f in required if f not in fns]
if missing:
    print(f"\nWARNING - Still missing: {missing}")
else:
    print("\n✅ All required functions present!")
