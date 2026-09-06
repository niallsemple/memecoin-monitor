import json
from datetime import datetime, timezone

with open('paper_v6.json') as f:
    data = json.load(f)

closed = data.get('closed', [])
positions = data.get('positions', {})
cash = data.get('cash', 0)
bank_start = data.get('bank_start', 0)

print(f"Total tracked hits (live positions): {len(positions)}")
print(f"Total closed positions: {len(closed)}")
print(f"Cash: ${cash:,.2f} | Bank start: ${bank_start:,.2f}")

# Sort closed by exit time, most recent first
closed_sorted = sorted(closed, key=lambda x: x.get('exit_time', ''), reverse=True)

# Check for recently closed (last hour or so)
now = datetime.now(timezone.utc)
recent_closed = []
for c in closed_sorted[:20]:
    exit_time = c.get('exit_time', '')
    if exit_time:
        try:
            et = datetime.fromisoformat(exit_time.replace('Z', '+00:00'))
            age_hours = (now - et).total_seconds() / 3600
            if age_hours < 2:
                recent_closed.append((c, age_hours))
        except:
            pass

print(f"\nRecently closed (<2h): {len(recent_closed)}")
for c, age in recent_closed[:10]:
    ret = c.get('return_pct', 0)
    reason = c.get('exit_reason', 'unknown')
    name = c.get('name', c.get('token', '?'))
    chain = c.get('chain', '?')
    print(f"  {chain} {name} | reason: {reason} | return: {ret:+.1f}% | age: {age:.1f}h")

# Overall stats
if closed:
    wins = [c for c in closed if c.get('return_pct', 0) > 0]
    losses = [c for c in closed if c.get('return_pct', 0) <= 0]
    win_rate = len(wins) / len(closed) * 100
    avg_return = sum(c.get('return_pct', 0) for c in closed) / len(closed)
    expectancy = avg_return
    print(f"\nAll-time closed stats:")
    print(f"  Win rate: {len(wins)}/{len(closed)} = {win_rate:.1f}%")
    print(f"  Avg return: {avg_return:+.2f}%")
    print(f"  Expectancy: {expectancy:+.2f}%")
    if wins:
        print(f"  Avg win: {sum(c.get('return_pct', 0) for c in wins)/len(wins):+.2f}%")
    if losses:
        print(f"  Avg loss: {sum(c.get('return_pct', 0) for c in losses)/len(losses):+.2f}%")

# Live positions summary
print(f"\nLive positions ({len(positions)}):")
for addr, pos in list(positions.items())[:5]:
    name = pos.get('name', '?')
    chain = pos.get('chain', '?')
    ret = pos.get('return_pct', 0)
    print(f"  {chain} {name} | return: {ret:+.1f}%")
