"""Chat terminal."""

from agent import process

print("Assistant Touristique (tapez quit pour sortir)\n")

while True:
    try:
        msg = input("Vous : ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\nAu revoir.")
        break
    if not msg or msg.lower() in ("q", "quit", "exit"):
        print("Au revoir.")
        break
    r = process(msg, session_id="terminal")
    print(f"\nAgent : {r['message']}\n")
