from librouteros import connect

api = connect(
    username='admin',
    password='agvjrp333',
    host='192.168.4.1',
    port=8728
)

print("✅ Connected to MikroTik")

# find Alicia
target = next((q for q in api('/queue/simple/print') if q['name'] == 'PRIVATE-ALICIA'), None)

if not target:
    print("❌ Queue not found")
else:
    print(f"🎯 Found {target['name']} (ID: {target['.id']})")

    # try setting max-limit directly (CLI equivalent)
    print("⚙️ Forcing max-limit=0/0 (unlimited)...")
    api('/queue/simple/set', **{'.id': target['.id'], 'max-limit': '0/0'})

    # confirm
    updated = next((q for q in api('/queue/simple/print') if q['name'] == target['name']), None)
    print("🔎 After update:")
    import json
    print(json.dumps(updated, indent=2))
